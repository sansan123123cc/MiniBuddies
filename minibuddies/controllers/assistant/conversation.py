"""Character prompts and assistant conversations."""

import datetime
import json
import os
import random
import re
import shutil
import sys
import threading
import time
from PyQt5.QtCore import QTimer, Qt
from minibuddies.catalog import (
    AFF_NAME,
    AI_CHAT_TOPICS,
    ASK_HELLO,
    CHAR_BIO,
    CHAR_CALL,
    DEFAULT_CALL,
    FRANCHISE,
    OUTFIT_NAME,
    SQUADS,
    SQUAD_NAME,
    THINK_LINES,
)
from minibuddies.controllers.assistant.briefing import BriefingController
from minibuddies.controllers.assistant.desktop_link import DesktopLink
from minibuddies.controllers.assistant.history import AssistantHistory
from minibuddies.controllers.assistant.providers import AssistantProviders
from minibuddies.desktop import screen_for
from minibuddies.runtime import BASE, MCP_HOME


class AssistantController(BriefingController, DesktopLink, AssistantHistory, AssistantProviders):
    def char_prompt(self, char, q):
        lab = self.chars[char]["label"]
        grp = next((SQUAD_NAME.get(sq, sq) for sq, m in SQUADS.items() if char in m), "")
        alt = f"{char}@{self.outfit.get(char)}" in CHAR_BIO      # 변신·이격 모습이면 기본 모습 수다 대사는 빼기
        lines = list(dict.fromkeys([it[5][0] for it in (self.chars[char].get("persona") or [])][:8]
                                   + ([] if alt else self.CHAT.get(char, [])[:3])))
        of = OUTFIT_NAME.get(self.outfit.get(char), "") if char in self.outfits else ""
        sq = next((sq for sq, m in SQUADS.items() if char in m), "")
        fr = next((fn for fn, sqs in FRANCHISE if sq in sqs), "")
        nikke = sq in ("nikke", "honkai")          # 게임 캐릭터 (방송인 아님)
        who = f"'{lab}'" + (f"({fr}" + (f" {grp}" if grp and grp != lab and grp != fr and not nikke else "") + ")" if fr else "")
        key = f"{char}@{self.outfit.get(char)}"
        bio = CHAR_BIO.get(key) or CHAR_BIO.get(char, "")
        call = self.cfg.get("my_name") or CHAR_CALL.get(char) or DEFAULT_CALL.get(sq)
        alv = self.aff_level(self.aff(char))
        rel = ["아직 처음 만난 사이라 살짝 낯가림", "친구 사이", "친한 친구 사이라 편하게", "단짝이라 아주 다정하게", "나를 제일 좋아하는 최애 사이라 애정 듬뿍"][alv]
        return (f"너는 내 바탕화면에 사는 데스크톱 펫 {who}야." + (f" 지금 모습은 '{of}'." if of else "")
                + f" 나와의 사이: {AFF_NAME[alv]}({rel})."
                + (f" 캐릭터 설명: {bio}" if bio else "")
                + (" 평소 말버릇: " + " / ".join(lines) if lines else "") + " "
                + (f"나를 부를 때는 '{call}'(이)라고 불러 줘. " if call else
                   "나를 부를 때 함장·주인님 같은 특별한 호칭은 쓰지 말고, 그 캐릭터가 친구에게 말하듯 자연스럽게 대해 줘. ")
                + f"내 질문에 {lab}의 말투와 성격으로 대답해 줘. 다른 친구들과 말투가 겹치지 않게 {lab}만의 말버릇을 살려 줘. "
                + ("게임 캐릭터를 팬이 만든 펫으로서 귀엽게 롤플레이해 주면 돼. " if nikke else
                   "실제 방송인 본인이 아니라 팬이 만든 펫 캐릭터로서 귀엽게 롤플레이해 주면 돼. ")
                + f"그리고 대답을 마치기 전에 꼭 desktop-pet 의 pet_say 도구를 who='{lab}' 로 불러서, 대답의 핵심을 {lab} 말투로 1~3문장(150자 이내)으로 줄여 내 화면 속 {lab} 말풍선에 띄워 줘."
                f"\n\n내 질문: {q}")

    def plain_prompt(self, char, q, room):
        """ChatGPT·Gemini 용 프롬프트 (펫 조종 도구 없이 대답만) + 이 방에서 나눈 최근 이야기"""
        lab = self.chars[char]["label"]
        base = self.char_prompt(char, q).split("그리고 대답을 마치기 전에")[0]
        hist = self.cfg.get("ask_hist", {}).get(room, [])[-6:]
        h = ""
        if hist:
            me = self.cfg.get("my_name") or "나"
            h = "앞에서 나눈 이야기(기억해 두고 이어서 대답해 줘):\n" + "\n".join(f"{me}: {x[1]}\n{x[0]}: {x[2]}" for x in hist) + "\n\n"
        return (base + f"대답은 바탕화면 말풍선에 그대로 들어가니까, 마크다운·목록·그림 이모지 없이 {lab} 말투로 1~3문장(150자 이내)만 써 줘. "
                "♪ ♥ ~ ☆ 같은 문장 기호는 이모지가 아니니까 그 캐릭터 말버릇이면 꼭 살려서 써 줘. 파일을 읽거나 고치거나 명령을 실행하지는 마. "
                + ("최신 정보가 필요하면 인터넷 검색을 써도 돼. " if self.cfg.get("ask_web") else "")
                + f"(지금 시각: {datetime.datetime.now():%Y-%m-%d %H:%M})\n\n" + h + "내 질문: " + q)

    def hidden_prompt(self, char, q, extra=None):
        lab = self.chars[char]["label"]
        base = self.char_prompt(char, q).split("그리고 대답을 마치기 전에")[0]
        others = ", ".join(self.chars[c]["label"] for c in (self.roster or [self.mode]) if c != char)
        room = ("이 대화방은 바탕화면 친구들 모두와 함께 쓰는 방이야. 앞에서 다른 친구가 한 말도 기억하고 이어서 대답해 줘. 이번엔 네가 대답할 차례야. "
                if self.cfg.get("ask_room", "one") == "one" else "")
        return (base + room + f"대답은 바탕화면 말풍선에 그대로 들어가니까, 마크다운·목록·그림 이모지 없이 {lab} 말투로 1~3문장(150자 이내)만 써 줘. ♪ ♥ ~ ☆ 같은 문장 기호는 이모지가 아니니까 그 캐릭터 말버릇이면 꼭 살려서 써 줘. "
                + self.power_note(extra)
                + ("최신 정보가 필요하면 인터넷 검색(WebSearch/WebFetch)을 써도 돼. " if self.cfg.get("ask_web") else "")
                + (f"화면에는 친구들({others})도 있어. " if others else "")
                + "내가 다른 친구에게 말을 시키거나, 동작·춤·잠자기·합동 장면·단체 놀이·옷 갈아입기·멤버 바꾸기·노래 틀기를 원하면 "
                  "desktop-pet 도구(pet_status, pet_say, pet_action, pet_persona, pet_scene, pet_group_play, pet_outfit, pet_team, pet_notify, pet_music, pet_remind)로 실제로 시켜 줘. "
                  "'몇 시에 알려 줘', '몇 분 뒤에 알려 줘' 같은 부탁은 pet_remind 로 예약해 줘 (지금 시각: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + "). "
                  "노래를 추천해 달라거나 조건에 맞는 노래를 틀어 달라고 하면, 인터넷 검색으로 실제 유튜브 영상 링크를 찾아서(링크를 지어내지 말 것) "
                  "pet_music 의 songs=[{title, url}] 와 name(목록 이름)으로 넘겨 저장·재생해 줘. 검색을 못 쓰면 곡 제목만 추천하고 'AI 연결 탭에서 인터넷 검색을 켜 주면 바로 틀어 줄게'라고 말해 줘. "
                  f"단, 네({lab}) 대답 말풍선은 펫 프로그램이 알아서 띄우니까 pet_say 로 {lab} 에게는 보내지 마."
                "\n\n내 질문: " + q)

    def ask_mcp_config(self):
        """숨겨서 물을 때 Claude Code 가 펫을 조종할 수 있게 desktop-pet 연결 설정 파일을 만들어 둠"""
        try:
            dst = os.path.join(MCP_HOME, "pet_mcp.py")
            if not os.path.exists(dst):
                os.makedirs(MCP_HOME, exist_ok=True); shutil.copy(os.path.join(BASE, "pet_mcp.py"), dst)
            exe = sys.executable
            if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-11] + "python.exe"):
                exe = exe[:-11] + "python.exe"
            path = os.path.join(MCP_HOME, "ask", "mcp.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump({"mcpServers": {"desktop-pet": {"command": exe, "args": [dst]}}},
                      open(path, "w", encoding="utf-8"), ensure_ascii=False)
            return path
        except Exception as e:
            self.ask_log(f"mcp config error {e}")
            return None

    def merged_power(self, extra=None):
        """설정의 작업 권한 + (파일 던지기로) 이번 한 번만 허락한 폴더·권한"""
        power, dirs = self.ask_power_dirs()
        if extra:
            rank = {"none": 0, "read": 1, "files": 2, "full": 3}
            dirs = dirs + [d for d in extra.get("dirs", []) if d not in dirs]
            if rank.get(extra.get("power", "none"), 0) > rank.get(power, 0):
                power = extra["power"]
        return power, dirs

    def ask_power_dirs(self):
        power = self.cfg.get("ask_power", "none")
        dirs = [d for d in self.cfg.get("ask_dirs", []) if os.path.isdir(d)]
        if power == "files" and not dirs:
            power = "none"                               # 폴더를 안 골랐으면 파일 권한도 없음
        return power, dirs

    def power_note(self, extra=None):
        power, dirs = self.merged_power(extra)
        if power == "none":
            return "파일을 읽거나 명령을 실행하지는 마. "
        where = ", ".join(dirs)
        if power == "read":
            return f"이 폴더들 안의 파일은 읽기만 해도 돼(고치거나 새로 만들거나 명령 실행은 하지 마): {where}. "
        t = (f"내가 부탁하면 이 폴더들 안의 파일은 읽고, 고치고, 새로 만들어도 돼: {where}. " if dirs else "")
        t += ("그 폴더 밖의 파일은 건드리지 마. " if power == "files" else
              "부탁하면 명령 실행(프로그램·파일 열기, 변환 같은 작업)도 해도 돼. ")
        t += ("기존 파일을 고치거나 덮어쓰기 전에는 같은 폴더에 '원래이름.bak' 으로 백업부터 해 줘. "
              "파일·폴더 지우기, 프로그램 설치, 시스템·보안 설정 바꾸기, 돈이 드는 일, 비밀번호 입력 같은 되돌리기 어려운 일은 하지 말고 방법만 말해 줘. "
              "다 하면 무엇을 했는지 말풍선에 짧게 알려 줘. ")
        return t

    def ask_hidden(self, b, q, extra=None):
        """Claude Code 를 창 없이 실행해서 대답을 받아 말풍선에 띄움 (구독 사용량 안에서)"""
        import subprocess
        exe = self.claude_cli()
        lab = self.chars[b.char]["label"]
        engine = self.ask_engine()
        if engine == "codex" and not self.codex_cli():
            self.force_say(b, "ChatGPT(Codex)가 안 깔려 있어요… 환경설정 → AI 연결 → 'ChatGPT·Gemini 설치·연결 방법'을 봐 주세요!", raw=True)
            return
        if engine == "gemini" and not self.cfg.get("gemini_key"):
            self.force_say(b, "Gemini API 키가 없어요… 환경설정 → AI 연결에서 키를 넣어 주세요! (구글 AI 스튜디오에서 무료로 받을 수 있어요)", raw=True)
            return
        if engine == "claude" and not exe:
            self.force_say(b, "Claude Code 가 안 깔려 있어요… 환경설정 → AI 연결에서 'Claude 창 열기'로 바꾸거나 Claude Code 를 깔아 주세요!")
            return
        room = "_room" if self.cfg.get("ask_room", "one") == "one" else b.char   # 한 방(전원 공유) / 캐릭터마다 따로
        if getattr(self, "_ask_busy", {}).get(room):          # 같은 방에서 대답 중이면 차례 기다리기
            self._ask_wait = getattr(self, "_ask_wait", []) + [(b, q, extra)]
            b.say("잠깐만~ 앞에 질문 대답 중이야. 끝나면 바로 대답할게!", 10 ** 9, force=True)
            b.say_lock = 10 ** 9
            return
        self._ask_busy = {**getattr(self, "_ask_busy", {}), room: True}
        tl = THINK_LINES.get(f"{b.char}@{self.outfit.get(b.char)}") or THINK_LINES.get(b.char) or ["음… 생각 중…"]
        b.say(random.choice(tl), 10 ** 9, force=True)
        b.say_lock = 10 ** 9
        sess = self.cfg.get("ask_sessions", {}).get(room)
        work = os.path.join(MCP_HOME, "ask"); os.makedirs(work, exist_ok=True)
        prompt = self.hidden_prompt(b.char, q, extra)
        shot = None if (extra or engine != "claude") else self.grab_screen_for_ask(b, q, work)
        if shot:
            prompt += (f" 참고로 지금 내 화면을 캡처해 뒀어: {shot} (Read 도구로 열어 보고, 화면 얘기가 나오면 그걸 보고 대답해 줘."
                       " 화면에 보이는 개인 정보는 말풍선에 그대로 옮기지 마.)")
        args = [exe, "-p", prompt, "--output-format", "json"]
        mcfg = self.ask_mcp_config() if self.cfg.get("ask_control", True) else None
        tools = (["mcp__desktop-pet"] if mcfg else []) + (["WebSearch", "WebFetch"] if self.cfg.get("ask_web") else [])
        if shot:
            tools += ["Read"]
        power, dirs = self.merged_power(extra)
        if power == "read":                              # 던진 파일 읽기만
            tools += ["Read", "Glob", "Grep", "LS"]
            for d in dirs:
                args += ["--add-dir", d]
        if power in ("files", "full"):                   # 작업 권한: 고른 폴더 안 파일 읽기·고치기
            tools += ["Read", "Edit", "MultiEdit", "Write", "Glob", "Grep", "LS"]
            for d in dirs:
                args += ["--add-dir", d]
        if power == "full":                              # + 명령 실행 (프로그램 켜기 등)
            tools += ["Bash", "PowerShell"]
        if mcfg:                                         # 다른 친구들에게도 시킬 수 있게
            args += ["--mcp-config", mcfg, "--strict-mcp-config"]
        if tools:
            args += ["--allowedTools", ",".join(tools)]
        if sess:
            args += ["--resume", sess]                      # 앞에서 나눈 이야기를 기억 (한 방이면 모두의 이야기)
        self.ask_log(f"hidden ask {lab}: {q}")
        if engine != "claude":
            pprompt = self.plain_prompt(b.char, q, room)
            ename = "ChatGPT" if engine == "codex" else "Gemini"
        def work_thread():
            out, err, sid = "", "", None
            if engine != "claude":
                try:
                    out, err = self.run_codex(pprompt, work) if engine == "codex" else self.run_gemini(pprompt)
                except subprocess.TimeoutExpired:
                    err = "시간 초과"
                except Exception as e:
                    err = str(e)
                self.claude_history("물어보기(" + ename + ")", lab, q, out, err)
                def done2():
                    self._ask_busy.pop(room, None)
                    wait = [w for w in getattr(self, "_ask_wait", []) if w[0] in self.buddies]
                    if wait:
                        self._ask_wait = wait[1:]
                        QTimer.singleShot(300, lambda w=wait[0]: self.ask_hidden(*w))
                    else:
                        self._ask_wait = []
                    if out:
                        hs = self.cfg.setdefault("ask_hist", {}).setdefault(room, [])
                        hs.append([lab, q[:300], out[:400]]); del hs[:-6]
                        self.save_cfg()
                        self.chat_log(lab, q, out)
                        self.add_aff(b, 4)
                    if b not in self.buddies:
                        return
                    b.say_lock = 0
                    if not out:
                        self.ask_log(f"hidden error ({ename}): {err}")
                        low = (err or "").lower()
                        if engine == "codex" and ("login" in low or "auth" in low or "401" in low or "sign in" in low):
                            msg = "ChatGPT 로그인이 필요해요! PowerShell 에서  codex login  을 한 번 실행해 주세요."
                        elif engine == "gemini" and ("키" in err or "key" in low):
                            msg = "Gemini API 키를 확인해 주세요! (환경설정 → AI 연결)"
                        elif "429" in low or "quota" in low or "limit" in low:
                            msg = f"{ename} 사용량이 잠깐 다 찼어요… 조금 뒤에 다시 물어봐 주세요!"
                        else:
                            msg = f"앗, 대답을 못 받았어요… ({(err or '')[:60]})"
                        self.force_say(b, msg, raw=True)
                        return
                    self.ask_log(f"hidden answer {lab} ({ename}): {out[:200]}")
                    self.force_say(b, out[:300] + ("…" if len(out) > 300 else ""))
                    b.set("happy", 60) if b.surface else None
                    if extra and extra.get("done"):
                        extra["done"](out)
                self.uiq.put(done2)
                return
            try:
                r = subprocess.run(args, capture_output=True, cwd=work, timeout=(600 if power != "none" else 240),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                txt = r.stdout.decode("utf-8", "replace").strip()
                try:
                    j = json.loads(txt)
                    out, sid = (j.get("result") or "").strip(), j.get("session_id")
                    if j.get("is_error"):
                        err = out or "error"
                except Exception:
                    out = txt
                if r.returncode != 0 and not out:
                    err = r.stderr.decode("utf-8", "replace").strip()[-300:] or f"exit {r.returncode}"
            except subprocess.TimeoutExpired:
                err = "시간 초과"
            except Exception as e:
                err = str(e)
            self.claude_history("물어보기", lab, q, out, err)
            def done():
                self._ask_busy.pop(room, None)
                wait = [w for w in getattr(self, "_ask_wait", []) if w[0] in self.buddies]
                if wait:                                         # 기다리던 다음 질문
                    self._ask_wait = wait[1:]
                    QTimer.singleShot(300, lambda w=wait[0]: self.ask_hidden(*w))
                else:
                    self._ask_wait = []
                if sid:
                    self.cfg.setdefault("ask_sessions", {})[room] = sid; self.save_cfg()
                if out:
                    self.chat_log(lab, q, out)
                    self.add_aff(b, 4)
                if b not in self.buddies:
                    return
                b.say_lock = 0
                if err and not out:
                    self.ask_log(f"hidden error: {err}")
                    if sess and "session" in err.lower():          # 예전 대화가 없어졌으면 새로 시작
                        self.cfg.get("ask_sessions", {}).pop(room, None); self.save_cfg()
                    low = err.lower()
                    msg = ("Claude Code 로그인이 필요해요! PowerShell 에서 claude 를 한 번 실행해서 로그인해 주세요."
                           if "login" in low or "auth" in low or "credit" in low else f"앗, 대답을 못 받았어요… ({err[:60]})")
                    self.force_say(b, msg, raw=True)
                    return
                self.ask_log(f"hidden answer {lab}: {out[:200]}")
                self.force_say(b, out[:300] + ("…" if len(out) > 300 else ""))
                b.set("happy", 60) if b.surface else None
                if extra and extra.get("done"):
                    extra["done"](out)
            self.uiq.put(done)
        threading.Thread(target=work_thread, daemon=True).start()

    def ask_claude(self, b):
        """캐릭터를 따닥 → 질문 입력 → Claude 새 대화를 그 캐릭터 설정으로 열기"""
        from PyQt5.QtWidgets import QInputDialog
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        import urllib.parse
        if b not in self.buddies or getattr(self, "_asking", False):
            return
        lab = self.chars[b.char]["label"]
        self._asking = True
        try:
            hk = f"{b.char}@{self.outfit.get(b.char)}"
            b.say(random.choice(ASK_HELLO.get(hk) or ASK_HELLO.get(b.char) or [f"{lab}한테 궁금한 거 있어?", "응? 뭐든 물어봐!"]), 200)
            dlg = QInputDialog()
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
            dlg.setWindowTitle(f"{lab}에게 물어보기")
            eng = self.ask_engine()
            hidden = eng == "gemini" or (self.cfg.get("ask_mode") or ("hidden" if self.ask_ready() else "window")) == "hidden"
            dlg.setLabelText(f"{lab}에게 물어볼 말 " + ("(대답은 말풍선으로 와요)" if hidden else "(ChatGPT 창이 열려요)" if eng == "codex" else "(Claude 창이 열려요)"))
            dlg.resize(460, 120)
            g = b.scr()
            dlg.move(int(max(g.left(), min(g.right() - 480, b.cx - 230))), int(max(g.top(), b.fy - 160)))
            if not dlg.exec_():
                return
            q = dlg.textValue().strip()
            if not q:
                return
            if hidden:
                self.ask_hidden(b, q)
                return
            enc = urllib.parse.quote(self.char_prompt(b.char, q), safe="")
            if eng == "codex":                               # ChatGPT 창으로
                QDesktopServices.openUrl(QUrl.fromEncoded(("https://chatgpt.com/?q=" + urllib.parse.quote(self.char_prompt(b.char, q).split("그리고 대답을 마치기 전에")[0] + "\n\n내 질문: " + q, safe="")).encode("ascii")))
                if b in self.buddies:
                    b.say("ChatGPT 한테 물어보고 올게~", 150)
                return
            ok = False
            if self.cfg.get("ask_where", "app") == "app":
                ok = QDesktopServices.openUrl(QUrl.fromEncoded(("claude://claude.ai/new?q=" + enc).encode("ascii")))
            if not ok:
                QDesktopServices.openUrl(QUrl.fromEncoded(("https://claude.ai/new?q=" + enc).encode("ascii")))
            if b in self.buddies:
                b.say("Claude 한테 물어보고 올게~", 150)
            if self.cfg.get("ask_send", True):
                self._send_clicked = False
                self.ask_log(f"opened ask for {lab}")
                QTimer.singleShot(1200, self.auto_send)
        finally:
            self._asking = False

    # ── 화면 같이 보기 (물어보기) ─────────────────────────────
    SCREEN_WORDS = ("화면", "이거", "이게", "여기", "저거", "에러", "오류", "창에", "보이는", "스크린", "캡처", "읽어")

    def grab_screen_for_ask(self, b, q, work):
        mode = self.cfg.get("ask_screen", "auto")
        if mode == "off" or (mode == "auto" and not any(w in q for w in self.SCREEN_WORDS)):
            return None
        try:
            sc = screen_for(b.char)
            pm = sc.grabWindow(0)
            if pm.width() > 1600:
                pm = pm.scaledToWidth(1600, Qt.SmoothTransformation)
            path = os.path.join(work, "screen.png")
            pm.save(path, "PNG")
            return path
        except Exception:
            return None

    # ── 캐릭터끼리 수다 (Claude, 켜고 끄기 + 하루 횟수 제한) ─────────────────────────────
    def ai_chat_ready(self):
        if not self.cfg.get("ai_chat", False) or getattr(self, "_ai_chat_busy", False) or self.group or self.scene:
            return False
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        st = self.cfg.get("ai_chat_count", {})
        if st.get("day") != today:
            st = {"day": today, "n": 0}; self.cfg["ai_chat_count"] = st
        if st["n"] >= int(self.cfg.get("ai_chat_max", 5)):
            return False
        gap = 60 * int(self.cfg.get("ai_chat_gap", 40))
        return time.time() - getattr(self, "_ai_chat_t", 0) > gap

    def start_ai_chat(self, force=False):
        """화면 속 두 친구가 Claude 로 짧은 수다를 나눔 (대사는 말풍선으로 번갈아)"""
        import subprocess
        exe = self.claude_cli()
        if not exe or getattr(self, "_ai_chat_busy", False):
            return False
        live = [b for b in self.buddies if b.surface and b.drag is None and b.state not in self.BUSY]
        chars = list({b.char: b for b in live}.values())
        if len(chars) < 2 and force:
            chars = list({b.char: b for b in self.buddies}.values())
        if len(chars) < 2:
            return False
        a, b = random.sample(chars, 2)
        la, lb = self.chars[a.char]["label"], self.chars[b.char]["label"]
        def bio(x):
            k = f"{x.char}@{self.outfit.get(x.char)}"
            lines = [it[5][0] for it in (self.chars[x.char].get("persona") or [])][:4]
            return (CHAR_BIO.get(k) or CHAR_BIO.get(x.char, "")) + (" 말버릇 예: " + " / ".join(lines) if lines else "")
        call = self.cfg.get("my_name") or CHAR_CALL.get(a.char) or DEFAULT_CALL.get(next((sq for sq, m in SQUADS.items() if a.char in m), ""), "") or "주인"
        topic = random.choice(AI_CHAT_TOPICS)
        prompt = (f"데스크톱 펫으로 내 바탕화면에서 같이 사는 두 친구 '{la}'와 '{lb}'의 짧은 잡담을 써 줘. "
                  f"{la}: {bio(a)}\n{lb}: {bio(b)}\n"
                  f"주제: {topic}. 지금 시각 {datetime.datetime.now():%H:%M}. 화면 주인은 '{call}'(이)라고 불러. "
                  "각자 원래 말투를 정확히 살리고, 귀엽고 다정한 분위기로. 4~6줄, 한 줄은 40자 이내, 둘이 번갈아 말하기. "
                  "도로롱은 '도로/도로롱/롱' 소리만 냄. 그림 이모지는 쓰지 말고 ♪ ~ ! 같은 기호는 괜찮아. "
                  f'다른 설명 없이 JSON 배열만 출력: [{{"who": "{la}", "line": "..."}}, {{"who": "{lb}", "line": "..."}}]')
        self._ai_chat_busy = True
        self._ai_chat_t = time.time()
        st = self.cfg.setdefault("ai_chat_count", {"day": datetime.datetime.now().strftime("%Y-%m-%d"), "n": 0})
        st["n"] = st.get("n", 0) + 1; self.save_cfg()
        work = os.path.join(MCP_HOME, "ask"); os.makedirs(work, exist_ok=True)
        def worker():
            lines = []
            try:
                r = subprocess.run([exe, "-p", prompt, "--output-format", "json"], capture_output=True, cwd=work, timeout=150,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                txt = r.stdout.decode("utf-8", "replace").strip()
                try:
                    txt = json.loads(txt).get("result") or txt
                except Exception:
                    pass
                m = re.search(r"\[.*\]", txt, re.S)
                if m:
                    lines = [x for x in json.loads(m.group(0)) if isinstance(x, dict) and x.get("line")][:6]
            except Exception as e:
                self.ask_log(f"ai chat error {e}")
            self.claude_history("친구 잡담", la + " · " + lb, prompt, "\n".join(str(x) for x in (lines or [])))
            self.uiq.put(lambda: self.play_ai_chat(a, b, la, lb, lines))
        threading.Thread(target=worker, daemon=True).start()
        return True

    def play_ai_chat(self, a, b, la, lb, lines):
        self._ai_chat_busy = False
        if not lines or a not in self.buddies or b not in self.buddies:
            return
        try:
            with open(os.path.join(BASE, "대화기록.txt"), "a", encoding="utf-8-sig") as f:
                f.write(f"[{datetime.datetime.now():%m/%d %H:%M}] (친구들 수다)\n" +
                        "\n".join(f"{x.get('who')}: {x.get('line')}" for x in lines) + "\n\n")
        except Exception:
            pass
        done = {"v": False}
        def talk(_me=None, _o=None):
            if done["v"]:
                return
            done["v"] = True
            for i, x in enumerate(lines):
                who = a if str(x.get("who", "")).strip() == la else (b if str(x.get("who", "")).strip() == lb else (a, b)[i % 2])
                other = b if who is a else a
                def say(who=who, other=other, t=str(x.get("line"))[:80]):
                    if who in self.buddies:
                        if other in self.buddies and who.surface and who.drag is None and who.state not in self.BUSY:
                            who.vx = 0; who.goal = None; who.face = 1 if other.cx > who.cx else -1
                            who.set("chat", 110)
                        who.say(t, 125, force=True)
                QTimer.singleShot(i * 3800, say)
        if a.surface and b.surface and a.surface == b.surface and abs(a.cx - b.cx) > a.S * 1.2:
            a.go_to(b, "approach", arrive=lambda me, o: talk(), ticks=400)     # 다가가서 수다
            QTimer.singleShot(9000, talk)                                    # 못 만나도 9초 뒤엔 그 자리에서 수다
        else:
            talk()
