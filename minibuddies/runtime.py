"""Application paths, Qt startup and crash reporting."""

import datetime
import os
import shutil
import sys
import threading


def _fix_qt_plugins():
    try:
        import PyQt5
        src = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
        if not os.path.isdir(src):
            src = os.path.join(os.path.dirname(PyQt5.__file__), "Qt", "plugins")
        if not src.isascii():
            dst = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "RabbitPet", "plugins")
            if not os.path.isdir(os.path.join(dst, "platforms")):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            src = dst
        os.environ["QT_PLUGIN_PATH"] = src
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(src, "platforms")
    except Exception:
        pass
_fix_qt_plugins()


ENTRY_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "buddies.py")
BASE = getattr(sys, "_MEIPASS", os.path.dirname(ENTRY_SCRIPT))
CHARS_DIR = os.path.join(BASE, "chars")      # chars/<이름>/0.png ... + meta.json + name.txt


# ── 꺼짐 방지·원인 기록 ─────────────────────────────
# PyQt5 는 타이머·버튼 처리 중 예외가 하나라도 나면 프로그램을 통째로 꺼 버림(abort) → 조용히 사라지던 원인.
# 예외는 crash.log 에 적고 계속 돌게, 진짜 튕김(세그폴트)도 crash.log 에 남게.
CRASH_LOG = os.path.join(BASE, "crash.log")
_fault_f = None
def _crash_write(text):
    try:
        if os.path.exists(CRASH_LOG) and os.path.getsize(CRASH_LOG) > 512 * 1024:
            os.replace(CRASH_LOG, CRASH_LOG + ".old")
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
_crash_seen = {}
def _excepthook(tp, val, tb):
    import traceback
    msg = "".join(traceback.format_exception(tp, val, tb))
    n = _crash_seen.get(msg, 0); _crash_seen[msg] = n + 1
    if n < 3:                                         # 같은 오류가 매 틱 반복되면 3번만 적기
        _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 오류 (프로그램은 계속 실행)\n{msg}")
def _thread_hook(args):
    _excepthook(args.exc_type, args.exc_value, args.exc_traceback)


def install_crash_handlers():
    global _fault_f
    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook
    try:
        import faulthandler
        _fault_f = open(CRASH_LOG, "a", encoding="utf-8")
        faulthandler.enable(_fault_f)
    except Exception:
        pass


MCP_HOME = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet")
