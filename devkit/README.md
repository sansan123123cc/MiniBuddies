# devkit — 데스크톱 펫 의상 추가 작업 설명서 (예약 작업용)

저장소 sansan123123cc/pet (비공개). PC 본체 buddies.py(PyQt5) + 안드로이드 앱(android/…/com/minibuddies/pet, Kotlin). 둘 다 자동 업데이트.
**PC와 앱은 항상 같이 맞춘다.** 개인용 프로젝트이며 버튜버 캐릭터는 사용자 개인 사용 목적으로 확인됨.

## 의상 대기열 (위에서부터, 이미 있는 건 건너뜀)
폴더 이름 = chars/<캐릭터>@<의상키>. 있는지 확인: GitHub 탭에서 `fetch('/sansan123123cc/pet/raw/main/chars/<폴더>/0.png').status` (200=있음).

| 폴더 | 표시 이름(OUTFIT_NAME) | 디자인 출처 |
|---|---|---|
| dokcake@mk1 | MK-1 | 나무위키 '독케익' 문서의 MK-1 이미지 |
| dokcake@mk2 | MK-2 | 같은 문서 MK-2 |
| dokcake@mk3 | MK-3 | 같은 문서 MK-3 |
| arisa@shin | 신의상 | 나무위키 '아리사(버츄얼 유튜버)' 등 AESTHER 아리사 문서의 신의상 |
| karin@shin | 신의상 | AESTHER 카린 문서 신의상 |
| eris@shin | 신의상 | AESTHER 에리스 문서 신의상 |
| ellie@shin | 신의상 | AESTHER 엘리 문서 신의상 |
| arisa@anniv2 | 2주년 신의상 | 아리사 문서 2주년 의상 |
| karin@anniv2 | 2주년 신의상 | 카린 문서 2주년 의상 |
| eris@anniv2 | 2주년 신의상 | 에리스 문서 2주년 의상 |
| ellie@anniv2 | 2주년 신의상 | 엘리 문서 2주년 의상 |

- 독케익 MK-1~3 공통: 검은 피부, 붉은 눈, 강아지 귀, 이마의 세 번째 눈, 가운데 흰 브릿지(MK-4 기본은 흰 피부·흑안·왼쪽 브릿지·해골 핀). MK별 차이(옷·머리)는 문서 이미지 그대로.
- 문서에 해당 의상이 없거나 이미지를 못 찾으면 그 항목은 건너뛰고 보고에 적는다(지어내지 말 것).
- AESTHER 엘리는 **낮은 트윈테일**(긴 생머리 아님). 에리스는 거대 트윈테일, 토끼 인형.
- 의상키·OUTFIT_NAME이 buddies.py의 OUTFIT_NAME에 이미 다른 뜻으로 있으면 겹치지 않는 키로 바꾼다.

## 준비 (클라우드 작업 폴더 W=/home/claude/pet)
1. `mkdir -p $W/sheets $W/chars $W/check $W/devkit`
2. 이 폴더의 파일을 받는다: GitHub 탭에서 `https://github.com/sansan123123cc/pet/raw/main/devkit/<파일>` 로 이동 → get_page_text → Write 로 $W/devkit/<파일>에 저장.
   파일: stitchg.py, edgefix.py, despill.py, build.sh, prompts.js, chatgpt_helpers.js
3. SK = desktop-pet-maker 스킬의 scripts 폴더(`ls /root/.claude/skills/synced/*/desktop-pet-maker/scripts`). make_frames.py·rope_meta.py·contact_sheet.py 를 그대로 씀.
4. `pip install pillow numpy --break-system-packages` (없으면)

## ChatGPT로 시트 7장 만들기 (의상 하나당 새 대화)
- 견본 이미지: 아티팩트 https://claude.ai/artifact/TZBetFPtQUZg888H3oWFVb#<dok|arisa|karin|eris|ellie> 로 이동 → 3초 대기 → screenshot(scale 없이) → 이 이미지가 1번 첨부.
- 디자인 이미지: 나무위키 문서에서 해당 의상 그림을 찾아 그 이미지만 크게 보이게(이미지 링크 열기 등) → screenshot → 2번 첨부.
- ChatGPT 탭을 https://chatgpt.com/ 새 대화로 → upload_image 로 견본, 디자인 순서로 입력창에 드롭 → 썸네일 2개 확인.
- 헬퍼: chatgpt_helpers.js 와 prompts.js 내용을 javascript_tool 로 그대로 붙여 실행(eval/불러오기는 CSP에 막히니 코드 본문을 직접 붙여넣는다).
  - 1번 메시지: `sendp(mk(1,{outfitname:'MK-1',look:'<디자인 설명: 머리·눈·피부·옷·장식·색>'}))`
  - 2~7번: `sendp(mk(n, O.<캐릭터>))` (O.dokcake / O.arisa / O.karin / O.eris / O.ellie). 소품 색은 의상에 맞게 O 값을 바꿔도 됨.
  - 보낸 뒤 25초씩 기다리며 `busy()` 가 false 가 될 때까지. 결과를 screenshot 으로 직접 보고 확인: 칸 수, 같은 캐릭터인지, 견본 의상이 섞였는지, 글자/로고/남의 캐릭터(산리오·스벅 등) 없는지. 이상하면 그 시트만 다시 요청.
  - 사용량 제한 메시지가 뜨면 그 의상은 버리고(부분 시트는 쓰지 않음) 보고에 적고 종료.
- 캡처(뷰포트 1154x728 기준. 다르면 아래 숫자를 비율대로 조정):
  - 4x2 시트(1774x887 근처): `cap3(0)` → screenshot 저장(save_to_disk, scale 지정 금지) = A, `cap3(302)` → screenshot = B,
    `python3 $W/devkit/stitchg.py $W/sheets/<p>_sN.png 1456 728 302,0:B 0,0:A` → PIL 로 1296x648 리사이즈.
    (cap3 반환값 [자연W,자연H,표시폭,vpW,vpH]; 표시폭-vpW 가 두 번째 dx)
  - 4x3 시트(1448x1086 근처): `cap3(0)` 한 번 → `stitchg.py out 971 728 0,0:A` → 864x648 리사이즈 → `python3 $W/devkit/edgefix.py out`.
  - 다 찍으면 `document.getElementById('__ov')?.remove()`.
  - 시트 번호: s1 4x2, s2·s3·s4 4x3, s5·s6·s7 4x2.
- 프리픽스 p 는 짧게(예 dmk1, arshin). 

## 프레임 만들기
`cd $W && W=$W SK=<scripts경로> NAME=<한글 이름, 예: 독케익> bash devkit/build.sh <p> <캐릭터>@<의상키> 7@0.8 5@0.88 1 5`
→ 68 프레임(+meta/name). `check/<p>_all.png` 를 Read 로 보고 잘림·빠진 칸·초록 테두리·크기 튐을 확인. 문제 칸은 시트를 다시 받거나 해당 영역을 초록으로 칠하고 재빌드.

## 올리기 (GitHub 웹, API 없음)
1. 프레임: `cd $W && zip -qr /tmp/<폴더>.zip chars/<캐릭터>@<의상키>` (반드시 chars/ 경로 포함, 10MB 미만) → `/mnt/user-data/uploads/` 로 복사
   → GitHub 탭 `https://github.com/sansan123123cc/pet/upload/main/incoming` → find 로 file input → file_upload → `#commit-summary-input` 에 메시지 → "Commit changes" 클릭.
   manifest 워크플로가 zip 을 풀어 chars/ 에 넣는다(약 30~60초). `chars/<폴더>/0.png` 가 200 이 되면 성공.
2. 대사: buddies.py 의 `\n\n\ndef hour():` 바로 앞에 블록을 끼워 넣는다. 계춘회 의상(chune@silverdress 등)과 같은 형식:
   ```python
   OUTFIT_NAME.update({"mk1": "MK-1"})
   PERSONA["dokcake@mk1"] = PERSONA["dokcake"]          # 6번 시트를 기본과 같은 순서로 만들었으므로
   CHAR_BIO["dokcake@mk1"] = "…이 의상 설명 + 기본 말투…"
   THINK_LINES["dokcake@mk1"] = [...]; ASK_HELLO["dokcake@mk1"] = [...]; OUTFIT_LINES["dokcake@mk1"] = [...]
   ```
   먼저 buddies.py 에서 `chune@silverdress` 가 들어간 줄들을 읽어 실제로 어떤 사전에 어떤 키로 넣었는지 확인하고 똑같이 한다.
   방법: upload/main 페이지에서 `fetch('/sansan123123cc/pet/raw/main/buddies.py')` 로 원문 → JS 로 split(기준).length==2 확인 후 join → `new File([s],'buddies.py')` 를 DataTransfer 로 file input 에 넣고 change 이벤트 → 커밋 메시지 → Commit changes → 다시 fetch 해서 같은지 확인.
   (JS 결과에 `=`·`[`·`?` 가 많으면 "BLOCKED" 로 가려지니 출력할 땐 `.replace(/[=?\[\]&]/g,'~')`)
3. 맨 폴더(chars/dokcake 등)는 PC·앱 모두 자동으로 '기본 의상(basic)'으로 묶인다. roster.txt 는 바꿀 필요 없음.
4. 앱: 의상 데이터는 android 워크플로의 export_data 가 buddies.py 에서 뽑아 간다. Actions 탭에서 manifest·android-apk 가 성공(초록)인지 확인. 실패하면 로그를 읽고 고친다(PC·앱 함께).

## 마무리 보고
- 만든 의상, 건너뛴 의상(이유), 남은 대기열을 짧게 정리.
- 사용자 메모리 /areas/desktop-pet.md 가 있으면 진행 상황 한 줄 갱신.
