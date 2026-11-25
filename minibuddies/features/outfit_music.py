"""Music linked to an outfit change."""

import os


# ── 모습 전용 노래: chars/<캐릭터>@<모습>/song.mp3 가 있으면 그 모습으로 바뀔 때 한 번 틀어 줌 (다른 모습으로 바꾸면 멈춤)
#    예) 마리안 → 신부(라스트 어펙션) 변신 때 'Call my name, Again'
def _outfit_song_file(d):
    for e in (".mp3", ".m4a", ".ogg", ".wav"):
        p = os.path.join(d, "song" + e)
        if os.path.exists(p):
            return p
    return None


def _outfit_song_stop(self):
    cur = getattr(self, "_osong", None)
    self._osong = None
    if cur:
        try:
            cur[1].stop()
        except Exception:
            pass




# ── 변신 노래 켜고 끄기 (우클릭 → '변신 노래 틀기' 체크) — 끄면 모습을 바꿔도 노래 안 나옴, 설정 저장
def _osong_menu(self, top, who):
    try:
        ofs = self.outfits.get(who.char, {}) or {}
        if not any((v or {}).get("dir") and _outfit_song_file(v["dir"]) for v in ofs.values()):
            return
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return
        a = top.addAction("변신 노래 틀기 ♪")
        a.setCheckable(True)
        a.setChecked(bool(cfg.get("outfit_song", True)))

        def _t(on, self=self):
            self.cfg["outfit_song"] = bool(on)
            self.save_cfg()
            if not on:
                _outfit_song_stop(self)
        a.toggled.connect(_t)
    except Exception:
        pass

def install(App):
    """Attach the outfit music behavior to the application."""
    _apply_outfit_nosong = App.apply_outfit


    def _apply_outfit_song(self, base, of):
        prev = self.outfit.get(base)
        _apply_outfit_nosong(self, base, of)
        if prev == of:
            return
        cur = getattr(self, "_osong", None)
        if cur and cur[0] == base:
            _outfit_song_stop(self)
        if prev is None:  # 처음 켤 때는 안 틂 — 바꿔 입을 때만
            return
        if not (getattr(self, "cfg", None) or {}).get("outfit_song", True):  # 변신 노래 꺼 둠
            return
        d = (self.outfits.get(base, {}).get(of) or {}).get("dir")
        p = _outfit_song_file(d) if d else None
        if not p:
            return
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtCore import QUrl
            pl = QMediaPlayer()
            pl.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(p))))
            pl.setVolume(70)
            pl.play()
            self._osong = (base, pl)
        except Exception:
            self._osong = None


    App.apply_outfit = _apply_outfit_song
