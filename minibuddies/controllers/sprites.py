"""Sprite resolution and two levels of rendering cache."""

import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from minibuddies.catalog import FALLBACK


class SpriteCache:
    def resolve(self, char, f):
        """그림이 없는 프레임은 FALLBACK 을 따라가며 있는 그림으로 (아직 덜 그린 모습도 안 깨지게)"""
        if f in self.plugins.sprites:
            return f
        d = self.chars[char]["dir"]
        cache = self.chars[char].setdefault("_res", {})
        if f not in cache:
            g, seen = f, set()
            while not os.path.exists(os.path.join(d, f"{g}.png")) and g not in seen:
                seen.add(g)
                g = FALLBACK.get(g, 0)
            cache[f] = g
        return cache[f]

    def frame_bounds(self, char, frame):
        frame = self.resolve(char, frame)
        sprite = self.plugins.sprites.get(frame)
        return sprite.bounds if sprite else self.chars[char]["meta"].get(frame, {})

    def spix(self, f, char, S, face, dpr=1.0):
        """크기·방향에 맞춰 미리 부드럽게 줄여 둔 그림 (그릴 때마다 줄이지 않게)"""
        key = (char, f, S, face, dpr)
        pm = self._spix.get(key)
        if pm is not None:
            self._spix.move_to_end(key)
        else:
            while len(self._spix) > 700:
                self._spix.popitem(last=False)
            from PyQt5.QtGui import QTransform
            src = self.pix(f, char)
            px = max(1, int(round(S * dpr)))
            pm = src.scaled(px, px, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            if face < 0:
                pm = pm.transformed(QTransform().scale(-1, 1))
            pm.setDevicePixelRatio(dpr)
            self._spix[key] = pm
        return pm

    def pix(self, f, char):
        key = (char, f)
        pm = self._pix.get(key)
        if pm is None:
            while len(self._pix) > 400:
                self._pix.popitem(last=False)
            frame = self.resolve(char, f)
            sprite = self.plugins.sprites.get(frame)
            path = str(sprite.path) if sprite else os.path.join(self.chars[char]["dir"], f"{frame}.png")
            pm = self._pix[key] = QPixmap(path)
        else:
            self._pix.move_to_end(key)
        return pm
