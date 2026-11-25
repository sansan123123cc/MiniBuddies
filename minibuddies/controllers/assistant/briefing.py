"""Scheduling and rendering of assistant briefings."""

import datetime
import json
import os
import re
import threading
from minibuddies.catalog import CHAR_BIO
from minibuddies.runtime import BASE, MCP_HOME
from minibuddies.ui.dialogs import BriefingWindow


class BriefingController:
    # ── 관심사 브리핑: 키워드 5개까지, 하루 한 번 검색해서 알려 주기 ─────────────────────────────
    def brief_dir(self):
        d = os.path.join(BASE, "브리핑"); os.makedirs(d, exist_ok=True)
        return d

    def brief_due(self, now):
        if not self.cfg.get("brief_on", False) or not self.brief_keys() or getattr(self, "_brief_busy", False):
            return False
        if self.cfg.get("brief_last") == now.strftime("%Y-%m-%d"):
            return False
        try:
            hh, mm = [int(x) for x in str(self.cfg.get("brief_time", "09:00")).split(":")[:2]]
        except Exception:
            hh, mm = 9, 0
        return (now.hour, now.minute) >= (hh, mm)

    def brief_keys(self):
        return [k.strip() for k in self.cfg.get("brief_keys", []) if k and k.strip()][:5]

    def start_briefing(self, force=False):
        import subprocess
        keys = self.brief_keys()
        sp = ([b for b in self.buddies if b.surface] or self.buddies or [None])[0]
        if not keys:
            if sp:
                self.force_say(sp, "브리핑 받을 관심사 키워드를 먼저 정해 줘~ (환경설정 → AI 연결 → 관심사 브리핑)", 8)
            return
        exe = self.claude_cli()
        if not exe:
            if sp:
                self.force_say(sp, "브리핑은 Claude Code 가 깔려 있어야 할 수 있어요…", 8)
            return
        if getattr(self, "_brief_busy", False):
            return
        self._brief_busy = True
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.cfg["brief_last"] = today; self.save_cfg()      # 실패해도 하루에 한 번만 자동 시도
        if sp and force:
            sp.say("관심사 소식 찾아볼게~ 조금만 기다려!", 150)
        who = sp.char if sp else (self.roster or [self.mode])[0]
        lab = self.chars[who]["label"]
        style = (CHAR_BIO.get(f"{who}@{self.outfit.get(who)}") or CHAR_BIO.get(who) or "")[:400]
        past = self.brief_history(today)
        prompt = (f"오늘은 {datetime.datetime.now():%Y년 %m월 %d일}이야. 다음 관심사 키워드 각각에 대해 인터넷 검색(WebSearch, 필요하면 WebFetch)으로 "
                  "최근 1~2일 사이의 새 소식·화제를 찾아서 정리해 줘. 소식이 없으면 '새 소식 없음'이라고 써. 지어내지 말고, 검색으로 확인한 것만.\n"
                  "키워드: " + " / ".join(keys) + "\n\n"
                  + (("아래는 최근 며칠 동안 이미 전한 브리핑이야. 여기 나온 소식과 같은 내용(같은 사건·발표·기사를 다른 매체가 다시 쓴 것 포함)은 전부 빼고, "
                      "처음 나온 소식만 골라 줘. 같은 사건이라도 새 진전(결과 발표·수치 변화·공식 입장 등)이 있으면 그 진전만 '(후속)'을 붙여 써 줘. "
                      "검색할 때도 아래와 겹치지 않는 다른 각도로 찾아봐. 빼고 나니 남는 게 없으면 그 키워드는 '새 소식 없음'.\n"
                      "──── 이미 전한 브리핑 ────\n" + past + "\n──── 여기까지 ────\n\n") if past else "")
                  + "결과는 아래 두 부분으로, 다른 말 없이 정확히 이 형식으로 써 줘.\n"
                  "===SHORT===\n"
                  f"(바탕화면 캐릭터 '{lab}'가 말풍선으로 전할 한 줄 브리핑. 새로 찾은 소식만으로, {lab} 말투로 2문장, 120자 이내, 마크다운·이모지 없이. 전부 새 소식이 없으면 그렇다고 짧게. 캐릭터 설정: {style})\n"
                  "===FULL===\n"
                  "(키워드마다 '■ 키워드' 제목 아래 핵심 소식 2~4개를 '- ' 로 시작하는 한두 줄 요약으로, 각 줄 끝에 (출처: 링크). 일반 텍스트로.)")
        long_ = len(prompt) > 6000                 # 명령줄 길이 한도(특히 claude.cmd 8191자) → 길면 표준입력으로 넘김
        args = [exe, "-p"] + ([] if long_ else [prompt]) + ["--output-format", "json", "--allowedTools", "WebSearch,WebFetch"]
        stdin_data = prompt.encode("utf-8") if long_ else None
        work = os.path.join(MCP_HOME, "brief"); os.makedirs(work, exist_ok=True)
        self.ask_log("briefing start: " + ", ".join(keys))
        def worker():
            out, err = "", ""
            try:
                r = subprocess.run(args, capture_output=True, cwd=work, timeout=900, input=stdin_data,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                txt = r.stdout.decode("utf-8", "replace").strip()
                try:
                    j = json.loads(txt); out = (j.get("result") or "").strip()
                    if j.get("is_error"):
                        err = out or "error"
                except Exception:
                    out = txt
                if r.returncode != 0 and not out:
                    err = r.stderr.decode("utf-8", "replace").strip()[-200:] or f"exit {r.returncode}"
            except subprocess.TimeoutExpired:
                err = "시간 초과"
            except Exception as e:
                err = str(e)
            self.claude_history("관심사 브리핑", lab, "키워드: " + ", ".join(keys), out, err)
            self.uiq.put(lambda: self.brief_done(out, err, keys, today))
        threading.Thread(target=worker, daemon=True).start()

    def brief_history(self, today, days=3, limit=2000):
        """최근 며칠 치 브리핑 내용 (오늘 이미 받은 것도 포함 — 다시 받을 때 겹치지 않게)"""
        try:
            fs = sorted(f for f in os.listdir(self.brief_dir()) if re.match(r"\d{4}-\d{2}-\d{2}\.txt$", f))
        except Exception:
            return ""
        older = [f for f in fs if f[:10] < today][-days:]
        pick = older + [f for f in fs if f[:10] == today]
        parts = []
        for f in pick:
            try:
                t = open(os.path.join(self.brief_dir(), f), encoding="utf-8-sig").read()
            except Exception:
                continue
            body = t.split("\n\n", 1)[-1].strip()
            body = re.sub(r"\(출처:[^)]*\)", "", body)            # 링크는 빼서 짧게
            parts.append(f"[{f[:10]}]\n" + body[:limit])
        return "\n\n".join(parts)

    def brief_done(self, out, err, keys, today):
        self._brief_busy = False
        sp = ([b for b in self.buddies if b.surface] or self.buddies or [None])[0]
        if err and not out:
            self.ask_log("briefing error: " + err)
            if sp:
                self.force_say(sp, f"브리핑을 못 가져왔어… ({err[:50]}) 메뉴에서 '지금 브리핑 받기'로 다시 해 줘!", 10)
            return
        short, full = "", out
        mm = re.search(r"===SHORT===\s*(.*?)\s*===FULL===\s*(.*)", out, re.S)
        if mm:
            short, full = mm.group(1).strip(), mm.group(2).strip()
        short = re.sub(r"[*#`>]", "", short).strip() or "오늘의 관심사 브리핑이 도착했어!"
        path = os.path.join(self.brief_dir(), f"{today}.txt")
        try:
            if os.path.exists(path):                       # 같은 날 다시 받으면 덮어쓰지 않고 아래에 이어 붙이기
                with open(path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n──── 추가 브리핑 {datetime.datetime.now():%H:%M} ────\n{full}\n")
            else:
                with open(path, "w", encoding="utf-8-sig") as f:
                    f.write(f"관심사 브리핑 — {today}\n키워드: {', '.join(keys)}\n\n{full}\n")
        except Exception as e:
            self.ask_log(f"briefing save error: {e}")
        self.ask_log("briefing done")
        w = getattr(self, "brief_win", None)
        if w is not None and w.isVisible():                # 보기 창이 열려 있으면 새 브리핑으로 바로 갱신
            w.reload(select=f"{today}.txt")
        if sp:
            self.ground(sp); sp.vx = 0; sp.set("wave", 120)
            self.force_say(sp, f"[브리핑] {short[:220]} (자세한 건 우클릭 → 관심사 브리핑 → 오늘 브리핑 보기)")

    def open_briefing(self):
        fs = sorted(f for f in os.listdir(self.brief_dir()) if f.endswith(".txt"))
        if not fs:
            sp = ([b for b in self.buddies if b.surface] or self.buddies or [None])[0]
            if sp:
                sp.say("아직 받은 브리핑이 없어~ '지금 브리핑 받기'를 눌러 봐!", 120)
            return
        w = getattr(self, "brief_win", None)
        if w is None:
            w = self.brief_win = BriefingWindow(self)
        w.reload(select=fs[-1])
        w.show(); w.raise_(); w.activateWindow()
