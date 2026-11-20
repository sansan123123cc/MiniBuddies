# -*- coding: utf-8 -*-
"""데스크톱 펫 ↔ Claude 연결용 MCP 서버 (표준 입출력, 추가 설치 필요 없음)
Claude 데스크톱이 이 파일을 실행하면, 켜져 있는 펫 프로그램들(127.0.0.1)에 명령을 전달한다.
"""
import sys, os, json, glob, urllib.request

HOME = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet", "instances")
PROTO = "2025-06-18"

def instances():
    out = []
    for f in sorted(glob.glob(os.path.join(HOME, "*.json"))):
        try:
            info = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if call(info["port"], {"op": "ping"}, timeout=1.5).get("ok"):
            out.append(info)
        else:
            try:
                os.remove(f)                       # 꺼진 펫의 흔적 정리
            except Exception:
                pass
    return out

def call(port, payload, timeout=6):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"연결 실패: {e}"}

def pick(app, who=None):
    ins = instances()
    if not ins:
        return []
    if app:
        ins = [i for i in ins if app.lower() in i["app"].lower()] or ins
    if who:
        w = str(who).lower()
        hit = [i for i in ins if any(w == k.lower() or w in v.lower() for k, v in i.get("chars", {}).items())]
        ins = hit or ins
    return ins

S = lambda **p: {"type": "object", "properties": p}
STR = lambda d: {"type": "string", "description": d}
APP = STR("어느 펫 프로그램에 보낼지 (예: stellive, bingha). 비우면 알아서")
WHO = STR("캐릭터 이름 또는 id (예: 리제, lize, 빙하유). 비우면 화면 전원/아무나")
TOOLS = [
    ("pet_status", "켜져 있는 데스크톱 펫 프로그램과 화면 속 캐릭터, 쓸 수 있는 동작·합동 장면·의상 목록을 본다. 다른 도구를 쓰기 전에 먼저 부르면 좋다.",
     S(app=APP), lambda a: {"op": "status"}),
    ("pet_say", "사용자 화면 속 캐릭터 머리 위에 말풍선을 띄운다. 사용자가 클릭해서 닫을 때까지 남아 있다. 캐릭터로서 대답할 때는 대답 요약을 이걸로 꼭 보여 준다.",
     {**S(text=STR("할 말 (300자 이내, 1~3문장 권장)"), who=WHO, seconds={"type": "number", "description": "몇 초 뒤 자동으로 사라지게 하려면 지정. 비우면 사용자가 닫을 때까지 유지"}, app=APP), "required": ["text"]},
     lambda a: {"op": "say", "text": a["text"], "who": a.get("who"), "seconds": a.get("seconds")}),
    ("pet_notify", "작업 완료 알림처럼, 캐릭터들이 만세하며 말풍선으로 알려 준다.",
     {**S(text=STR("알릴 내용"), who=WHO, app=APP), "required": ["text"]},
     lambda a: {"op": "notify", "text": a["text"], "who": a.get("who")}),
    ("pet_action", "캐릭터에게 동작을 시킨다: cheer, wave, dance, sing, sleep, nap, cry, pout, happy, surprise, yawn, eat, read, kiss, milk, angry, dizzy. 니케 캐릭터는 shoot(뒷모습 사격), 마리안·도로시는 transform(모더니아·도로롱 변신/해제)도 됨",
     {**S(action=STR("동작 이름"), who=WHO, app=APP), "required": ["action"]},
     lambda a: {"op": "action", "action": a["action"], "who": a.get("who")}),
    ("pet_persona", "캐릭터만의 개성 동작을 시킨다 (pet_status 의 persona 목록 참고). index(0~7) 또는 대사 일부(name)로 고르고, 비우면 아무거나.",
     S(who=WHO, index={"type": "integer"}, name=STR("개성 동작 대사 일부"), app=APP),
     lambda a: {"op": "persona", "who": a.get("who"), "index": a.get("index"), "name": a.get("name")}),
    ("pet_scene", "그룹 합동 장면을 튼다 (예: group=어비스, scene=karaoke). scene 을 비우면 아무거나.",
     {**S(group=STR("그룹 이름 (1기생/유니버스/클리셰/어비스/니케)"), scene=STR("장면 키 (pet_status 의 scenes 참고)"), app=APP), "required": ["group"]},
     lambda a: {"op": "scene", "group": a["group"], "scene": a.get("scene")}),
    ("pet_group_play", "단체 놀이/둘이 놀기: train, tower, photo, hands, chat, karaoke, tag, snack, dance, nap, greet",
     {**S(kind=STR("놀이 이름"), app=APP), "required": ["kind"]},
     lambda a: {"op": "group", "kind": a["kind"]}),
    ("pet_team", "합본에서 화면에 나올 멤버를 바꾼다. group(예: 클리셰) 또는 members(이름 목록).",
     S(group=STR("그룹 이름"), members={"type": "array", "items": {"type": "string"}}, app=APP),
     lambda a: {"op": "team", "group": a.get("group"), "members": a.get("members", [])}),
    ("pet_outfit", "옷 갈아입기 (빙하유 등 의상이 여러 벌인 캐릭터). outfit 을 비우면 아무거나.",
     S(who=WHO, outfit=STR("의상 이름 (예: 한복, 웨딩드레스, 경찰관)"), app=APP),
     lambda a: {"op": "outfit", "who": a.get("who"), "outfit": a.get("outfit", "")}),
    ("pet_music", "노래 틀기. 저장된 유튜브 노래·재생목록을 틀거나(name, pet_status 의 music 목록), url 로 유튜브 링크를 직접 틀거나, "
     "추천 리스트를 저장해서 이어서 재생한다(songs=[{title, url}] + name). songs 의 url 은 인터넷 검색으로 찾은 실제 유튜브 영상 링크만 넣고 지어내지 말 것. "
     "재생은 화면에 창이 안 뜨는 숨김 플레이어로 되고, 그동안 펫들이 춤춘다. stop=true 면 노래 끄기.",
     S(name=STR("저장된 노래 이름 또는 새로 저장할 목록 이름"), url=STR("유튜브 링크 (선택)"),
       songs={"type": "array", "description": "추천 곡 목록", "items": {"type": "object", "properties": {"title": {"type": "string"}, "url": {"type": "string"}}, "required": ["url"]}},
       play={"type": "boolean", "description": "songs 를 저장한 뒤 바로 틀지 (기본 true)"}, stop={"type": "boolean"}, app=APP),
     lambda a: {"op": "music", "name": a.get("name"), "url": a.get("url"), "songs": a.get("songs"), "play": a.get("play", True), "stop": a.get("stop", False)}),
    ("pet_remind", "예약 알림: 정한 시각(또는 몇 분 뒤)에 캐릭터가 말풍선으로 알려 준다. time='15:00' 또는 '2026-11-01 09:30', 아니면 minutes=10. "
     "who 로 알려 줄 캐릭터 지정 가능. list=true 면 예약 목록, cancel=번호(0부터) 면 취소.",
     S(text=STR("알려 줄 내용"), time=STR("HH:MM 또는 YYYY-MM-DD HH:MM"), minutes={"type": "number"}, who=WHO,
       list={"type": "boolean"}, cancel={"type": "integer"}, app=APP),
     lambda a: {"op": "remind", "text": a.get("text", ""), "time": a.get("time"), "minutes": a.get("minutes"), "who": a.get("who"),
                "list": a.get("list", False), "cancel": a.get("cancel")}),
    ("pet_alarm", "특별 이벤트 알림을 바로 틀기: morning, lunch, snack, off, night",
     {**S(kind=STR("알림 종류"), app=APP), "required": ["kind"]},
     lambda a: {"op": "alarm", "kind": a["kind"]}),
]

def run_tool(name, args):
    log(f"call {name} {json.dumps(args, ensure_ascii=False)[:200]}")
    t = next((t for t in TOOLS if t[0] == name), None)
    if not t:
        return {"ok": False, "error": f"없는 도구: {name}"}
    payload = t[3](args)
    ins = pick(args.get("app"), args.get("who"))
    if not ins:
        return {"ok": False, "error": "켜져 있는 데스크톱 펫이 없어요. RUN_....bat 으로 펫을 먼저 켜 주세요."}
    if name == "pet_status" or (name == "pet_notify" and not args.get("who")):
        return {i["app"]: call(i["port"], payload) for i in ins}
    return call(ins[0]["port"], payload)

def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def log(t):
    try:
        os.makedirs(os.path.dirname(HOME), exist_ok=True)
        with open(os.path.join(os.path.dirname(HOME), "mcp.log"), "a", encoding="utf-8") as f:
            import datetime
            f.write(f"{datetime.datetime.now():%m-%d %H:%M:%S} {t}\n")
    except Exception:
        pass

def main():
    log("started " + sys.executable)
    try:
        sys.stdin.reconfigure(encoding="utf-8"); sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid, method = msg.get("id"), msg.get("method")
        if mid is None:                               # 알림(notifications/*)은 대답 안 함
            continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": msg.get("params", {}).get("protocolVersion", PROTO),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "desktop-pet", "version": "1.0"},
                "instructions": "사용자의 윈도우 바탕화면을 돌아다니는 캐릭터 펫을 조종한다. 먼저 pet_status 로 누가 있는지 보고, 작업이 끝나면 pet_notify 로 알려 주면 좋다."}})
            try:                                       # 켜져 있는 펫들에게 '연결됐어요' 인사
                for i in instances():
                    call(i["port"], {"op": "hello"}, timeout=2)
            except Exception:
                pass
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                {"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]}})
        elif method == "tools/call":
            p = msg.get("params", {})
            res = run_tool(p.get("name"), p.get("arguments") or {})
            ok = not (isinstance(res, dict) and res.get("ok") is False)
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not ok}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})

if __name__ == "__main__":
    main()
