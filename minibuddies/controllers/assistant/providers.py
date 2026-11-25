"""Assistant selection and provider command execution."""

import json
import os
import shutil


class AssistantProviders:
    def claude_cli(self):
        """설치된 Claude Code(claude.exe) 찾기"""
        cand = [shutil.which("claude"), shutil.which("claude.exe"),
                os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "claude", "claude.exe"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")]
        return next((c for c in cand if c and os.path.exists(c)), None)

    def codex_cli(self):
        """설치된 ChatGPT Codex CLI(codex) 찾기"""
        cand = [shutil.which("codex"), shutil.which("codex.cmd"), shutil.which("codex.exe"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "codex.cmd"),
                os.path.join(os.path.expanduser("~"), ".local", "bin", "codex.exe")]
        return next((c for c in cand if c and os.path.exists(c)), None)

    def ask_engine(self):
        """물어보기에 쓸 AI: 고른 게 있으면 그것, 없으면 깔린 것 중에서"""
        e = self.cfg.get("ask_engine")
        if e in ("claude", "codex", "gemini"):
            return e
        if self.claude_cli():
            return "claude"
        if self.codex_cli():
            return "codex"
        return "gemini" if self.cfg.get("gemini_key") else "claude"

    def ask_ready(self):
        e = self.ask_engine()
        return bool(self.claude_cli() if e == "claude" else self.codex_cli() if e == "codex" else self.cfg.get("gemini_key"))

    def run_codex(self, prompt, work):
        """ChatGPT Codex CLI 를 창 없이 실행 → (대답, 오류)"""
        import subprocess
        exe = self.codex_cli()
        if not exe:
            return "", "codex 없음"
        last = os.path.join(work, "codex_last.txt")
        try:
            os.remove(last)
        except Exception:
            pass
        args = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-o", last, "-"]
        r = subprocess.run(args, input=prompt.encode("utf-8"), capture_output=True, cwd=work, timeout=300,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = ""
        try:
            out = open(last, encoding="utf-8", errors="replace").read().strip()
        except Exception:
            out = r.stdout.decode("utf-8", "replace").strip()
        err = "" if out else (r.stderr.decode("utf-8", "replace").strip()[-300:] or f"exit {r.returncode}")
        return out, err

    def run_gemini(self, prompt):
        """Gemini API(구글 AI 스튜디오 키)로 대답 받기 → (대답, 오류). 무료 키는 검색이 안 되면 검색 없이 다시"""
        import urllib.request, urllib.error
        key = (self.cfg.get("gemini_key") or "").strip()
        if not key:
            return "", "Gemini API 키 없음"
        models = [m for m in [self.cfg.get("gemini_model"), "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"] if m]
        err = ""
        for m in models:
            for web in ([True, False] if self.cfg.get("ask_web") else [False]):
                body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
                if web:
                    body["tools"] = [{"google_search": {}}]
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-goog-api-key": key})
                try:
                    with urllib.request.urlopen(req, timeout=120) as r:
                        j = json.loads(r.read().decode("utf-8"))
                    parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                    out = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                    if out:
                        return out, ""
                    err = "빈 대답"
                except urllib.error.HTTPError as e:
                    try:
                        msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
                    except Exception:
                        msg = ""
                    err = f"{e.code} {msg}"[:200]
                    if e.code in (401, 403) and "API key" in msg:
                        return "", "API 키가 맞지 않아요"
                    if e.code == 404:
                        break                                    # 없는 모델 → 다음 모델
                except Exception as e:
                    err = str(e)[:200]
        return "", err
