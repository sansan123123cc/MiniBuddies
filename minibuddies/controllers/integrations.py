"""Desktop file drops and companion applications."""

import json
import os
import random
import shutil
import threading
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QMenu, QMessageBox
from minibuddies.catalog import APP_NAME, DROP_LINES, IMAGE_EXT, MY_APPS, VIDEO_EXT


class ExternalAppsController:
    # ── 파일 던지기: 캐릭터 위에 파일을 놓으면 요약·정리·변환 ─────────────────────────────
    DROP_FORMATS = ["txt", "md", "csv", "json", "html", "xlsx", "docx", "pdf", "png", "jpg"]

    def _drop_dlg_flags(self, w):
        w.setWindowFlags(w.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(60, self.raise_popups)

    def file_drop(self, b, paths):
        from PyQt5.QtWidgets import QInputDialog
        if b not in self.buddies:
            return
        paths = [os.path.normpath(x) for x in paths if os.path.exists(x)][:10]
        if not paths:
            return
        vids = [x for x in paths if os.path.splitext(x)[1].lower() in VIDEO_EXT]     # 영상·음악 → 코덱무관플레이어
        imgs = [x for x in paths if os.path.splitext(x)[1].lower() in IMAGE_EXT]     # 사진 → 이름표
        def _has_imgs(d):                        # 사진이 들어 있는 폴더인지 (바로 아래 + 하위 폴더 조금만 훑기)
            try:
                subs = []
                for i, e in enumerate(os.scandir(d)):
                    if i > 800:
                        break
                    if e.is_file() and os.path.splitext(e.name)[1].lower() in IMAGE_EXT:
                        return True
                    if e.is_dir() and len(subs) < 20:
                        subs.append(e.path)
                for s in subs:
                    for i, e in enumerate(os.scandir(s)):
                        if i > 300:
                            break
                        if e.is_file() and os.path.splitext(e.name)[1].lower() in IMAGE_EXT:
                            return True
            except Exception:
                pass
            return False
        img_dirs = [x for x in paths if os.path.isdir(x) and _has_imgs(x)]   # 사진 폴더 → 이름표로 바로 열기
        cl = bool(self.claude_cli())
        busy = bool(getattr(self, "_ask_busy", {}).get("_drop"))
        if not cl and not (vids or imgs or img_dirs):
            self.force_say(b, "파일 정리는 Claude Code 가 깔려 있어야 할 수 있어요… (PowerShell 에서 claude 설치·로그인)", 10)
            return
        if busy and not (vids or imgs or img_dirs):
            self.force_say(b, "앞에 맡긴 파일 아직 하는 중이야~ 끝나면 다시 줘!", 6)
            return
        if b.surface is None:
            self.ground(b)
        b.vx = 0; b.goal = None; b.set("cheer", 60)
        b.say(random.choice(DROP_LINES["got"]), 400)
        folder = [x for x in paths if os.path.isdir(x)]
        names = ", ".join(os.path.basename(x) or x for x in paths)
        m = QMenu()
        m.setWindowFlags(m.windowFlags() | Qt.WindowStaysOnTopHint)
        m.aboutToShow.connect(lambda: QTimer.singleShot(30, self.raise_popups))
        title = m.addAction(f"{names[:40]}{'…' if len(names) > 40 else ''}"); title.setEnabled(False)
        m.addSeparator()
        a_play = m.addAction("코덱무관플레이어로 재생") if vids else None
        a_tag = m.addAction("이름표로 이 폴더 열기 (이미지 파일명 편집)" if img_dirs else "이름표로 열기 (이미지 파일명 편집)") if (imgs or img_dirs) else None
        if a_play is not None or a_tag is not None:
            m.addSeparator()
        a_sum = m.addAction("요약해 줘 (말풍선으로)")
        a_note = m.addAction("정리해서 새 파일로 만들어 줘 (원본은 그대로)")
        a_conv = m.addAction("다른 형식으로 바꿔 줘…")
        a_dir = m.addAction("폴더 정리해 줘 (종류별로 나누기)") if folder else None
        a_free = m.addAction("직접 부탁하기…")
        if not cl or busy:                       # Claude Code 가 없거나 앞의 일을 하는 중이면 정리 메뉴는 잠금
            for x in (a_sum, a_note, a_conv, a_dir, a_free):
                if x is not None:
                    x.setEnabled(False)
        m.addSeparator()
        m.addAction("그만두기")
        act = m.exec_(QCursor.pos())
        if act is not None and act is a_play:
            self.open_app("player", vids, b)
            return
        if act is not None and act is a_tag:
            self.open_app("nametag", (img_dirs or sorted({os.path.dirname(x) for x in imgs}))[:1], b)
            return
        if act is None or act not in (a_sum, a_note, a_conv, a_dir, a_free):
            b.say("응, 알겠어~", 60)
            return
        dirs = sorted({x if os.path.isdir(x) else os.path.dirname(x) for x in paths})
        plist = "\n".join(paths)
        rule = ("원본 파일은 지우거나 덮어쓰지 말고, 결과는 원본과 같은 폴더에 새 파일로 만들어 줘(이름이 겹치면 뒤에 _2 처럼 붙이기). "
                "다 하면 어떤 파일을 만들었는지 말풍선에 짧게 알려 줘. ")
        if act is a_sum:
            need, q = "read", ("이 파일(들)을 읽고 핵심만 요약해 줘. 폴더면 안에 뭐가 있는지 훑어보고 알려 줘.\n" + plist)
        elif act is a_note:
            need, q = "files", ("이 파일(들)을 읽고 내용을 보기 좋게 정리한 문서를 새로 만들어 줘(제목·소제목·핵심 요점 정리, 이름은 '원래이름_정리.md'). "
                                + rule + "\n" + plist)
        elif act is a_conv:
            dlg = QInputDialog(); self._drop_dlg_flags(dlg)
            dlg.setWindowTitle("다른 형식으로 바꾸기"); dlg.setLabelText("어떤 형식으로 바꿀까? (예: txt, md, csv, xlsx, pdf, png…)")
            dlg.setComboBoxItems(self.DROP_FORMATS); dlg.setComboBoxEditable(True)
            if not dlg.exec_() or not dlg.textValue().strip():
                return
            fmt = dlg.textValue().strip().lstrip(".")
            simple = fmt.lower() in ("txt", "md", "csv", "json", "html")
            need = "files" if simple else "full"
            q = (f"이 파일(들)을 {fmt} 형식으로 바꿔 줘. " + rule +
                 ("" if simple else "필요하면 컴퓨터에 이미 깔린 프로그램·파이썬으로 변환해도 되지만, 새 프로그램을 설치하지는 마. 못 하면 방법만 알려 줘. ")
                 + "\n" + plist)
        elif act is a_dir:
            need, q = "full", ("이 폴더 안의 파일들을 종류별(문서·이미지·영상·음악·압축·기타 등)로 하위 폴더를 만들어 옮겨서 정리해 줘. "
                               "파일은 절대 지우지 말고, 같은 이름이 있으면 덮어쓰지 말고 이름 뒤에 _2 를 붙여. 하위 폴더 안 파일은 건드리지 마. "
                               "옮긴 목록은 그 폴더에 '정리기록.txt' 로 남기고(되돌릴 수 있게), 말풍선에는 몇 개를 어디로 옮겼는지만 짧게.\n"
                               + "\n".join(folder))
        else:
            dlg = QInputDialog(); self._drop_dlg_flags(dlg)
            dlg.setWindowTitle("이 파일로 뭘 해 줄까?"); dlg.setLabelText(f"{names[:50]} 로 할 일"); dlg.resize(460, 120)
            if not dlg.exec_() or not dlg.textValue().strip():
                return
            need, q = "files", (dlg.textValue().strip() + "\n대상 파일: \n" + plist + "\n" + rule)
        if not self.drop_allowed(need, dirs):
            b.say("알겠어, 안 건드릴게~ (환경설정 → AI 연결 → 작업 권한)", 120)
            return
        b.say(random.choice(DROP_LINES["start"]), 150)
        self.ask_log(f"file drop {need}: {names}")
        self.ask_hidden(b, "[파일 던지기] " + q, extra={"dirs": dirs, "power": need})

    def drop_allowed(self, need, dirs):
        """설정한 작업 권한으로 모자라면 이번 한 번만 허락받기"""
        if need == "read":
            return True                                   # 파일을 직접 던져 준 것 = 읽어도 된다는 뜻
        power, have = self.ask_power_dirs()
        inside = all(any(os.path.normcase(d).startswith(os.path.normcase(h)) for h in have) for d in dirs)
        ok = (power == "full" and inside) if need == "full" else (power in ("files", "full") and inside)
        if ok:
            return True
        what = ("파일을 새로 만들고 옮기거나, 컴퓨터에 깔린 프로그램으로 변환하는 명령 실행" if need == "full"
                else "파일 읽기와 새 파일 만들기")
        box = QMessageBox(QMessageBox.Question, "이번 한 번만 허락",
                          f"이번 한 번만 이 폴더에서 {what}을 해도 될까요?\n\n" + "\n".join(dirs) +
                          "\n\n원본을 고칠 땐 .bak 백업을 먼저 하고, 지우기·설치는 하지 않아요.",
                          QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        self._drop_dlg_flags(box)
        return box.exec_() == QMessageBox.Yes

    def app_path(self, key):
        """내 앱이 깔려 있으면 exe 경로 (윈도우 프로그램 목록 → 기본 설치 폴더 순으로 찾음)"""
        a = MY_APPS[key]
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for sub in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                    try:
                        k = winreg.OpenKey(root, sub)
                    except OSError:
                        continue
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            sk = winreg.OpenKey(k, winreg.EnumKey(k, i))
                            dn = str(winreg.QueryValueEx(sk, "DisplayName")[0]).lower()
                        except OSError:
                            continue
                        if not any(m in dn for m in a["match"]):
                            continue
                        for val in ("DisplayIcon", "InstallLocation"):
                            try:
                                v = str(winreg.QueryValueEx(sk, val)[0]).split(",")[0].strip().strip('"')
                            except OSError:
                                continue
                            cands = [v] if v.lower().endswith(".exe") else [os.path.join(v, e) for e in a["exe"]]
                            for c in cands:
                                if os.path.isfile(c) and "uninst" not in os.path.basename(c).lower():
                                    return c
        except Exception:
            pass
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")
        for d in a["dirs"]:
            for e in a["exe"]:
                c = os.path.join(base, d, e)
                if os.path.isfile(c):
                    return c
        return None

    def _app_say(self, who, text, secs=6):
        try:
            if who is not None and who in self.buddies:
                self.force_say(who, text, secs)
            elif getattr(self, "tray", None) is not None:
                self.tray.showMessage(APP_NAME, text)
        except Exception:
            pass

    def open_app(self, key, files=None, b=None):
        """내 앱(코덱무관플레이어·이름표) 켜기 — 안 깔려 있으면 최신 설치 파일을 받아 조용히 설치까지"""
        import subprocess
        a = MY_APPS[key]
        who = b if b is not None else (random.choice(self.buddies) if self.buddies else None)
        exe = self.app_path(key)
        if exe:
            try:
                subprocess.Popen([exe] + list(files or []), cwd=os.path.dirname(exe))
                if who is not None and who in self.buddies:
                    who.say(random.choice(a["hi"]), 120)
            except Exception as ex:
                self._app_say(who, f"{a['name']} 못 켰어… ({str(ex)[:60]})")
            return
        if getattr(self, "_app_inst", None):
            self._app_say(who, "지금 설치하는 중이야~ 조금만 기다려!")
            return
        box = QMessageBox(QMessageBox.Question, APP_NAME,
                          f"{a['name']}가 아직 안 깔려 있어요.\n펫이 최신 설치 파일을 받아서 바로 설치할까요? (1~2분)",
                          QMessageBox.Yes | QMessageBox.No)
        if box.exec_() != QMessageBox.Yes:
            return
        self.install_app(key, files, who)

    def install_app(self, key, files=None, who=None):
        import subprocess, tempfile, urllib.request
        a = MY_APPS[key]
        self._app_inst = key
        self._app_res = None
        self._app_say(who, f"{a['name']} 받아 오는 중… 잠깐만!", 8)

        def work():
            err = ""
            try:
                hdr = {"User-Agent": "minibuddies-pet"}
                req = urllib.request.Request(f"https://api.github.com/repos/{a['repo']}/releases/latest",
                                             headers=dict(hdr, Accept="application/vnd.github+json"))
                rel = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
                asset = next(x for x in rel.get("assets", [])
                             if x["name"].startswith(a["asset"]) and x["name"].lower().endswith(".exe"))
                dst = os.path.join(tempfile.gettempdir(), asset["name"])
                with urllib.request.urlopen(urllib.request.Request(asset["browser_download_url"], headers=hdr),
                                            timeout=60) as r:
                    with open(dst, "wb") as f:
                        shutil.copyfileobj(r, f)
                subprocess.run([dst] + a["silent"], timeout=900)
            except StopIteration:
                err = "설치 파일을 못 찾았어"
            except Exception as ex:
                err = str(ex)[:80] or "알 수 없는 오류"
            self._app_res = (key, err, list(files or []), who)

        def poll():
            if self._app_res is None:
                return
            self._app_poll.stop()
            k, err, fl, w = self._app_res
            self._app_inst = None
            nm = MY_APPS[k]["name"]
            if err:
                self._app_say(w, f"{nm} 설치 실패… ({err})", 10)
            elif self.app_path(k):
                self._app_say(w, f"{nm} 설치 끝! 켤게~", 5)
                self.open_app(k, fl, w)
            else:
                self._app_say(w, f"설치는 끝났는데 {nm}를 못 찾겠어… 시작 메뉴에서 켜 줘!", 10)

        self._app_poll = QTimer(timeout=poll)
        self._app_poll.start(700)
        threading.Thread(target=work, daemon=True).start()
