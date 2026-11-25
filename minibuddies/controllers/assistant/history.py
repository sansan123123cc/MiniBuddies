"""Assistant conversation and diagnostic logs."""

import datetime
import json
import os
from minibuddies.runtime import BASE, _crash_write
from minibuddies.ui.dialogs import HistoryDialog, claude_hist_dir


class AssistantHistory:
    def chat_log(self, lab, q, a):
        """나눈 대화를 펫 폴더의 '대화기록.txt' 에 차곡차곡"""
        try:
            me = self.cfg.get("my_name") or "나"
            with open(os.path.join(BASE, "대화기록.txt"), "a", encoding="utf-8-sig") as f:
                f.write(f"[{datetime.datetime.now():%m/%d %H:%M}] {me} → {lab}: {q}\n{lab}: {a}\n\n")
        except Exception:
            pass

    def claude_history(self, kind, who, q, out, err=""):
        """Claude Code 에 보낸 것(인풋)과 받은 답(아웃풋)을 날짜별 파일로 남김 → 트레이 'Claude 이력 보기'"""
        if not self.cfg.get("claude_history", True):
            return
        try:
            d = os.path.join(BASE, "claude_history")
            os.makedirs(d, exist_ok=True)
            now = datetime.datetime.now()
            row = {"t": now.isoformat(timespec="seconds"), "kind": kind, "who": who,
                   "q": str(q or "").strip(), "out": str(out or "").strip(), "err": str(err or "")}
            with open(os.path.join(d, f"{now:%Y-%m-%d}.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def open_claude_history(self):
        """Claude 이력 관리 창 (검색·날짜/종류 필터·복사·삭제·내보내기)"""
        d = getattr(self, "hist_dlg", None)
        try:
            if d is not None and d.isVisible():
                d.reload(); d.raise_(); d.activateWindow()
                return
        except RuntimeError:
            pass
        try:
            self.hist_dlg = HistoryDialog(self)
            self.hist_dlg.show(); self.hist_dlg.raise_(); self.hist_dlg.activateWindow()
        except Exception:
            import traceback
            _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 이력 창 오류\n{traceback.format_exc()}")

    def open_claude_history_dir(self):
        d = claude_hist_dir()
        try:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
        except Exception:
            pass

    def ask_log(self, t):
        try:
            with open(os.path.join(BASE, "ask.log"), "a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now():%H:%M:%S} {t}\n")
        except Exception:
            pass
