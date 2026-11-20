# 계절 이벤트 코스튬 시트 작업 (2026-11-16~)

모든 캐릭터에 계절 이벤트 코스튬 4종을 그린다. 코드(PC buddies.py 이벤트 블록, 앱 Event.kt, export_data/prep_assets)는 이미 들어가 있음 —
**그림만 올리면 자동으로 PC·앱 둘 다 나온다.** 엘리시아(elysia@basic)로 시험 완료.

## 그림 규칙
- 캐릭터의 **기본 의상 폴더**에만 넣는다(ev_queue.txt 첫 칸). 어떤 옷을 입고 있어도 이벤트 땐 이 그림을 씀.
- 번호: 130~137 산타(xmas) / 138~145 한복(hanbok) / 146~153 할로윈(halloween) / 154~161 발렌타인(valentine)
- 칸 0 = 등장 포즈(기준 칸), 1~7 = 동작. 위치 정보는 같은 폴더의 `meta_event.json`.
- 우선순위: 크리스마스가 가장 급함(12/20~26). 한 캐릭터를 한 ChatGPT 대화에서 4장 연달아 뽑는 게 제일 효율적.

## 준비 (클라우드 작업 폴더 W=/home/claude/pet)
1. `mkdir -p $W/devkit $W/evsheets $W/chars_ev/chars $W/check $W/tmp_ev`
2. GitHub 탭(github.com 페이지)에서 아래 파일을 받아 `$W/devkit/` 에 저장:
   `fetch('/sansan123123cc/pet/raw/main/devkit/<파일>').then(r=>r.text())` 를 페이지에 `<pre>`로 띄우고 get_page_text → Write.
   파일: EVENT_README.md, event_prompts.js, ev_build.sh, ev_st.py, despill.py, ev_queue.txt, ev_done.txt
3. SK = desktop-pet-maker 스킬 scripts 폴더 (make_frames.py 사용). `pip install pillow numpy --break-system-packages` (없으면)
4. 할 캐릭터 고르기: ev_queue.txt 에서 ev_done.txt 에 없는 것 위에서부터.

## 한 캐릭터 진행 (id = 기본 폴더, name = 한글 이름)
1. **견본**: GitHub 탭에서 refov 붙여 넣고 실행 → `await refov('<id>')` → screenshot(scale 1) → 이 ID 를 기억
   ```js
   window.refov=async(id,fr)=>{fr=fr||[0,12,11,20];document.getElementById('__ov')?.remove();const d=document.createElement('div');d.id='__ov';d.style.cssText='position:fixed;inset:0;z-index:2147483647;background:#fff;display:flex;align-items:center;justify-content:center;gap:10px';const ok=[];for(const n of fr){const im=new Image();im.src='/sansan123123cc/pet/raw/main/chars/'+id+'/'+n+'.png';im.style.cssText='height:80vh;max-width:24vw;object-fit:contain';await new Promise(r=>{im.onload=()=>{ok.push(n);r()};im.onerror=r});d.appendChild(im)}document.body.appendChild(d);return ok.join(',')};
   ```
2. **ChatGPT 새 대화**: ChatGPT 탭에서 '새 채팅' 버튼 클릭(SPA라 도우미 유지) 또는 https://chatgpt.com/ 이동 후
   event_prompts.js 본문을 javascript_tool 로 그대로 붙여 실행(eval 말고 본문 직접) → `upload_image`(견본 ID, 입력창 좌표) → 썸네일 확인.
3. 시트 4장 차례로:
   - 1장째: `evsend(EVP('<name>','xmas'))`  2~4장째: `evsend(EVN('<name>','hanbok'))`, `'halloween'`, `'valentine'`
   - `await evwait(40000)` 을 'ready …' 가 나올 때까지 반복(보통 2~3분).
   - 캡처: `evtq(0)` → screenshot(**scale 1**, save_to_disk) → `evtq(1)` → 같은 방법 → `evtq(2)` → `evtq(3)` → `evun()`
     (browser_batch 로 한 번에. scale 을 낮추면 저장 파일도 작아지니 꼭 1)
   - 결과를 눈으로 확인: 8칸·같은 캐릭터·의상 일관·초록 배경·글자/로고 없음·전신. 이상하면 그 시트만 다시 요청.
   - 이어 붙이기(저장된 스크린샷 번호 a,b,c,d / 1774x887 시트, 뷰포트 1151x633 기준 오프셋):
     `python3 $W/devkit/ev_st.py $W/evsheets/<id>_<kind>.png 1774 887 a:0:0 b:623:0 c:0:254 d:623:254`
     (시트·뷰포트 크기가 다르면 evtq 결과의 OFF 값을 그대로 오프셋으로)
   - 프레임: `W=$W bash $W/devkit/ev_build.sh <id> <kind>` → `check/ev_<id>_<kind>.png` 를 Read 로 확인
4. 사용량 제한이 뜨면 그 캐릭터는 다 된 종류만 올리고(ev_done 에 종류만 적기) 종료.

## 올리기
- `cd $W/chars_ev && zip -qr /tmp/ev_<n>.zip chars/<id1> chars/<id2> …` (10MB 미만, 캐릭터 2~5명씩) → `/mnt/user-data/uploads/` 로 복사
  → GitHub `https://github.com/sansan123123cc/pet/upload/main/incoming` → find 로 file input → file_upload → `#commit-summary-input` → Commit changes.
- ev_done.txt 에 `<id>\t<종류들>\t<날짜>` 줄 추가 → `upload/main/devkit` 에 ev_done.txt 올리기(같은 방식).
- Actions 탭에서 manifest·android-apk 초록 확인. 실패하면 로그 읽고 원인 보고(코드 고칠 땐 PC·앱 같이).

## 특이 캐릭터
- 시부키(shibuki): 머리 위 뾰족한 두 개는 **고양이 귀가 아니라 머리카락을 세운 뿔(머리카락 뿔)**. 귀 안쪽 분홍색·털 넣지 말 것 → extra 에 `머리 위의 뾰족한 두 개는 동물 귀가 아니라 머리카락을 뾰족하게 세운 머리카락 뿔이야. 귀 안쪽 색이나 털 없이 머리카락과 같은 색·같은 결로만 그려.`
- 계춘회(chune@basic): 할로윈은 실제 2025 할로윈 의상 느낌으로 → `EVN('계춘회','halloween','할로윈 분장은 이 캐릭터의 실제 할로윈 의상(검은 토끼 귀, 트윈테일)으로.')`
- 도로롱 등 밈 생물(dorothy@doro, scarlet@hongbuk)은 기본 폴더가 아니라서 대상 아님.
- 홀로라이브 졸업 멤버(아쿠아·시온·카나타·클로에·아오)도 roster 에 있으면 그대로 진행.

## 마무리 보고
- 이번에 끝낸 캐릭터, 남은 수, 문제 있었던 시트. 사용자 메모리 /areas/desktop-pet.md 에 진행 한 줄.
