"""Installed application updates and built-in character selection."""

import os
import random
import threading
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox
from minibuddies.ui.picker import CharPicker
from minibuddies.updates import (
    upd_apply,
    upd_check,
    upd_fetch_manifest,
    upd_installed,
    upd_load,
    upd_path,
    upd_save_cfg,
    upd_selected,
)


class DistributionController:
    # ── 자동 업데이트 ─────────────────────────────
    def update_tick(self):
        if not os.path.exists(upd_path("update.json")):   # 설치 프로그램으로 깐 펫만 (원본·개발용 폴더는 조용히)
            return
        if upd_load("update.json").get("auto", True):
            self.check_update(quiet=True)

    def open_char_picker(self):
        """메뉴 '캐릭터 고르기': 쓰는 캐릭터만 남기고 나머지는 지우기 / 새로 받기"""
        if not os.path.exists(upd_path("update.json")):
            QMessageBox.information(None, "캐릭터 고르기", "설치 프로그램으로 깐 펫에서만 쓸 수 있어요.")
            return
        man = upd_load("manifest.json")
        sel = upd_selected()
        cur = upd_installed() if sel is None else sel
        dlg = CharPicker(man.get("files", {}), cur)
        if not dlg.exec_():
            return
        new = dlg.chosen()
        if new == cur and sel is not None:
            return
        uc = upd_load("update.json"); uc["chars"] = sorted(new); upd_save_cfg(uc)
        if self.upd_busy:
            return
        self.upd_busy = True
        who = self.buddies[0] if self.buddies else None
        if who:
            self.force_say(who, "고른 캐릭터로 바꾸는 중이야~ 잠깐만!", 6)

        def work():
            try:
                remote = upd_fetch_manifest()
                n = upd_apply(remote)
                self.upd_msg = "캐릭터 고르기 완료 (받은 파일 %d개)" % n
                self.ask_log("chars: " + self.upd_msg)
                self.uiq.put(lambda: QTimer.singleShot(1500, self.restart_self))
            except Exception as e:
                self.upd_msg = "캐릭터 받기 실패: %s" % e
                self.uiq.put(lambda: self.buddies and self.force_say(random.choice(self.buddies), self.upd_msg, 8))
            finally:
                self.upd_busy = False
        threading.Thread(target=work, daemon=True).start()

    def check_update(self, quiet=False, done_cb=None):
        """백그라운드에서 확인 → 새 버전이면 받아서 교체 → 펫 다시 켜기"""
        if self.upd_busy:
            return
        self.upd_busy = True

        def say(text, sticky=False):
            def f():
                if self.buddies:
                    self.force_say(random.choice(self.buddies), text, None if sticky else 6)
            self.uiq.put(f)

        def work():
            ok = False
            try:
                remote, msg = upd_check()
                if remote:
                    say("새 버전이 나왔어! 받는 중이야~ (v%s)" % remote.get("version", remote.get("build")))
                    n = upd_apply(remote)
                    msg = "업데이트 완료! v%s (파일 %d개)" % (remote.get("version", remote.get("build")), n)
                    ok = True
                self.upd_msg = msg
                self.ask_log("update: " + msg)
                if ok:
                    say(msg + " 잠깐 다시 켜질게~")
                    self.uiq.put(lambda: QTimer.singleShot(2500, self.restart_self))
                elif not quiet:
                    say(msg)
                elif "토큰" in msg and not getattr(self, "upd_warned", False):   # 토큰 문제는 한 번만 알려 줌
                    self.upd_warned = True
                    say(msg)
            except Exception as e:
                self.upd_msg = f"업데이트 실패: {e}"
                self.ask_log("update error: %s" % e)
                if not quiet:
                    say(self.upd_msg)
            finally:
                self.upd_busy = False
                if done_cb:
                    self.uiq.put(lambda: done_cb(self.upd_msg))
        threading.Thread(target=work, daemon=True).start()
