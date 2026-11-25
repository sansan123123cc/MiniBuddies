"""Outfit and transformation changes."""

import json
import os
import random
from PyQt5.QtCore import QTimer
from minibuddies.catalog import ALT_FROM, ALT_TF, DORO_MOTION_DIR, F, OUTFIT_LINES, TRANSFORM, persona_of
from minibuddies.runtime import CHARS_DIR
from minibuddies.ui.widgets import Burst


class OutfitController:
    def transform(self, base, to_alt=None):
        """마리안↔모더니아, 도로시↔도로롱: 변신 연출(9번 시트) 후 모습 바꾸기"""
        tf = TRANSFORM.get(base)
        if not tf or base not in self.outfits or tf["alt"] not in self.outfits[base]:
            return False
        cur = self.outfit.get(base)
        if to_alt is None:
            to_alt = cur != tf["alt"]
        target = tf["alt"] if to_alt else "basic"
        if cur == target:
            return False
        bs = [b for b in self.buddies if b.char == base and b.surface and b.state not in ("group", "gather", "train")]
        if not bs or not os.path.exists(os.path.join(self.chars[base]["dir"], "76.png")):
            self.set_outfit(base, target)
            return True
        go, arrive = (tf["go"], tf["arrive"]) if to_alt else (tf["back"], tf["home"])
        l0, l1, l2 = tf["lines"]

        def switched():
            self.apply_outfit(base, target)
            self.cfg.setdefault("outfit", {})[base] = target
            self.save_cfg()
            for b in bs:
                if b in self.buddies:
                    b.say(l1 if to_alt else l2, 130)
                    b.play_seq([(f, 16) for f in arrive] + [(F["walk"][0], 10)])
                    b.update()
            if base == "scarlet" and to_alt and random.random() < 0.5:   # 홍북이가 되자마자 도로롱이 있으면 가끔 사과 베기
                QTimer.singleShot(3500, self.apple_cut)
        for i, b in enumerate(bs):
            b.goal = None
            b.say(l0 if to_alt else "…", 90)
            b.play_seq([(f, 12) for f in go], after=switched if i == 0 else None)
        return True

    def has_tf(self, base, of):
        d = self.outfits.get(base, {}).get(of)
        return bool(d) and f"{base}@{of}" in ALT_TF and os.path.exists(os.path.join(d["dir"], "84.png"))

    def alt_chain(self, base, of):
        """기본에서 그 모습까지 변신 순서 (예: 도로시 해방 = 노스텔지어 → 해방)"""
        path, x = [], of
        while x and x != "basic" and x not in path and len(path) < 5:
            path.insert(0, x)
            x = ALT_FROM.get(f"{base}@{x}", "basic")
        return path

    def alt_transform(self, base, target):
        """니케 이격 변신: 정방향(84~91) / 풀 때 역방향 / 이격끼리는 거꾸로 풀었다가 다시 변신.
        ALT_FROM 이 있으면 그 모습을 거쳐서 (기본 → 노스텔지어 → 해방)"""
        cur = self.outfit.get(base)
        C, T = self.alt_chain(base, cur), self.alt_chain(base, target)
        k = 0
        while k < min(len(C), len(T)) and C[k] == T[k]:
            k += 1
        steps = [("rev", x) for x in reversed(C[k:])] + [("fwd", x) for x in T[k:]]
        if not any(self.has_tf(base, x) for _, x in steps):
            return False
        bs = [b for b in self.buddies if b.char == base and b.surface and b.state not in ("group", "gather", "train", "tower")]
        if not bs:
            return False

        def save(of):
            self.apply_outfit(base, of)
            self.cfg.setdefault("outfit", {})[base] = of
            self.save_cfg()

        def run(rest):
            live = [b for b in bs if b in self.buddies]
            if not rest or not live:
                for b in live:
                    b.play_seq([(F["walk"][0], 8)])
                return
            kind, x = rest[0]
            key = f"{base}@{x}"
            tf = self.has_tf(base, x)
            if kind == "rev":
                parent = ALT_FROM.get(key, "basic")
                if not tf:
                    save(parent); run(rest[1:]); return

                def undone():
                    save(parent)
                    if parent == "basic" and len(rest) == 1:
                        for b in live:
                            b.say(ALT_TF[key][2], 120)
                    run(rest[1:])
                for i, b in enumerate(live):
                    b.goal = None; b.vx = 0
                    b.play_seq([(f, 9) for f in range(91, 83, -1)], after=undone if i == 0 else None)
            else:
                save(x)
                if not tf:
                    for b in live:
                        b.say(random.choice(OUTFIT_LINES.get(key) or OUTFIT_LINES.get(base, ["짜잔~"])), 120)
                    run(rest[1:]); return

                def done():
                    for b in live:
                        if b in self.buddies:
                            b.say(ALT_TF[key][1], 130)
                    run(rest[1:])
                for i, b in enumerate(live):
                    b.goal = None; b.vx = 0
                    if i == 0:
                        b.say(ALT_TF[key][0], 80)
                    b.play_seq([(f, 11) for f in range(84, 90)] + [(f, 18) for f in (90, 91)],
                               after=done if i == 0 else None)
                    b.update()
        run(steps)
        return True

    def apply_outfit(self, base, of):
        data = dict(self.outfits[base][of])
        if base == "dorothy" and of == "doro" and self.cfg.get("doro_motion"):
            alt = os.path.join(CHARS_DIR, DORO_MOTION_DIR)      # 모션 버전 도로롱 (환경설정에서 켰을 때만)
            if os.path.exists(os.path.join(alt, "0.png")):
                data["dir"] = alt
                try:
                    raw = json.load(open(os.path.join(alt, "meta.json"), encoding="utf-8"))
                    data["meta"] = {int(k): v for k, v in raw["frames"].items()}
                    data["rope"] = raw.get("rope", {})
                except Exception:
                    pass
        data["persona"] = persona_of(f"{base}@{of}", data["dir"])
        self.chars[base] = data
        self.outfit[base] = of
        for k in [k for k in self._pix if k[0] == base]:
            del self._pix[k]
        for k in [k for k in self._spix if k[0] == base]:
            del self._spix[k]

    def set_outfit(self, base, of, say=True):
        """옷 갈아입기: 펑! 하고 바뀜"""
        if of not in self.outfits.get(base, {}) or self.outfit.get(base) == of:
            return
        tf = TRANSFORM.get(base)
        if say and tf and {of, self.outfit.get(base)} == {"basic", tf["alt"]} \
                and any(b.char == base and b.surface for b in self.buddies):
            self.transform(base, of == tf["alt"])         # 변신은 연출과 함께
            return
        if say and self.alt_transform(base, of):           # 니케 이격: 변신 연출(84~91)
            return
        self.apply_outfit(base, of)
        self.cfg.setdefault("outfit", {})[base] = of
        self.save_cfg()
        for b in self.buddies:
            if b.char == base:
                try:
                    Burst(b.cx, b.fy + b.S * 0.6, b.S * 0.9)
                except Exception:
                    pass
                if say and b.surface:
                    b.say(random.choice(OUTFIT_LINES.get(f"{base}@{of}") or OUTFIT_LINES.get(base, ["짜잔~"])), 120)
                b.update()

    def auto_outfit(self):
        if not self.outfits or not self.cfg.get("outfit_auto", True):
            return
        self.outfit_t += 1
        if self.outfit_t < random.randint(12, 25):          # 12~25분마다 한 번쯤
            return
        self.outfit_t = 0
        for base, ofs in self.outfits.items():
            if len(ofs) > 1 and any(b.char == base and b.surface for b in self.buddies):
                self.set_outfit(base, random.choice([o for o in ofs if o != self.outfit.get(base)]))
