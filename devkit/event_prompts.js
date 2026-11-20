// 계절 이벤트 코스튬 시트 프롬프트. EVP(이름, 종류, 추가설명) — 종류: xmas / hanbok / halloween / valentine
window.EVBASE=(name)=>'이 캐릭터('+name+')와 똑같은 그림체·얼굴·머리 모양·머리색·눈 색·머리 장식·신체 특징(귀·뿔·꼬리 등)·등신(2등신 SD)·선 굵기·채색을 그대로 지켜. 눈은 견본 크기 그대로(너무 크게 키우지 말기), 표정은 예쁘게. 4열 x 2행 그리드, 칸 크기 동일, 모든 칸 캐릭터 크기와 비율 동일(견본과 같은 2등신, 머리부터 발끝까지 전신이 칸 안에 다 들어오게), 방향 있는 동작은 전부 오른쪽을 보게, 배경은 완전 단색 순수 초록(#00FF00), 그림자·글자·칸 테두리 없이, 효과(눈송이·하트·반짝이 등)는 캐릭터 몸 가까이에만 조금. 8칸 모두 같은 의상. 가로로 넓은 이미지 한 장으로 완성해 줘.';
window.EVK={
 xmas:{c:'크리스마스 코스튬 시트',o:'옷만 이 캐릭터의 상징색이 살짝 들어간 귀여운 산타 의상(빨간 바탕에 흰 털 장식, 같은 디자인의 산타 모자)으로 갈아입혀.',
  k:'1) 산타 옷을 입고 정면을 보며 한 손을 흔들며 인사, 2) 리본 묶은 선물 상자를 두 손으로 앞으로 내밀기, 3) 하얀 선물 자루를 어깨에 메고 오른쪽으로 걸어가기, 4) 쪼그려 앉아 작은 눈사람을 만들기, 5) 서서 작은 크리스마스 케이크 조각을 포크로 맛있게 먹기, 6) 두 팔을 벌리고 하늘을 보며 내리는 눈에 기뻐하기(눈송이 몇 개), 7) 서서 금색 종(벨)을 흔들며 캐럴 부르기(음표 하나), 8) 바닥에 앉아 큰 크리스마스 양말을 꼭 안고 꾸벅꾸벅 졸기(Zz).'},
 hanbok:{c:'설날·추석 한복 시트',o:'옷만 이 캐릭터의 상징색을 살린 고운 한복(저고리와 치마, 옷고름)으로 갈아입혀. 머리 장식은 견본 그대로 두고 한복에 어울리는 작은 댕기나 꽃 장식 하나만 더해도 돼.',
  k:'1) 한복을 입고 정면을 보며 두 손을 배꼽 앞에 모으고 공손히 고개 숙여 인사, 2) 오른쪽을 향해 무릎 꿇고 두 손을 바닥에 모아 큰절(세배)하기, 3) 서서 복(福) 무늬 없는 빨간 복주머니를 두 손으로 앞으로 내밀기, 4) 앉아서 떡국 그릇을 들고 숟가락으로 먹기, 5) 서서 실패를 잡고 위를 보며 연 날리기(작은 방패연이 머리 위에), 6) 서서 윷가락 네 개를 위로 던지기, 7) 서서 송편이 담긴 작은 접시를 들고 웃기, 8) 서서 작은 노란 보름달을 올려다보며 두 손 모아 소원 빌기.'},
 halloween:{c:'할로윈 코스튬 시트',o:'옷만 이 캐릭터에게 가장 잘 어울리는 할로윈 분장 하나(마녀·뱀파이어·검은 고양이·유령·작은 악마·호박 중 하나)로 갈아입혀. 8칸 모두 같은 분장.',
  k:'1) 분장을 하고 정면을 보며 망토나 치마를 살짝 잡고 귀엽게 포즈, 2) 호박 모양 사탕 바구니를 두 손으로 앞으로 내밀기(트릭 오어 트릿), 3) 웃는 호박 등불을 들고 오른쪽으로 걸어가기, 4) 두 손을 들어 "왁!" 하고 귀엽게 놀래키기, 5) 서서 큰 막대사탕 먹기, 6) 옆에 나타난 작고 귀여운 유령에 깜짝 놀라 움찔하기, 7) 큰 호박 위에 걸터앉아 다리 흔들기, 8) 한 바퀴 빙글 돌며 망토나 치마가 휘날리기.'},
 valentine:{c:'발렌타인·화이트데이 시트',o:'옷은 견본의 평소 의상 그대로 두고, 그 위에 분홍 하트 무늬 앞치마를 두르고 머리에 작은 빨간 하트 핀 하나를 더해.',
  k:'1) 정면을 보며 수줍게 두 손을 등 뒤로 숨기고 서기(볼 살짝 발그레), 2) 리본 묶은 하트 모양 초콜릿 상자를 두 손으로 앞으로 내밀며 얼굴 빨개지기, 3) 서서 볼에 초콜릿을 살짝 묻히고 그릇의 초콜릿을 거품기로 젓기, 4) 초콜릿 상자를 한 손으로 내밀면서 고개를 반대쪽으로 홱 돌리고 눈을 감은 채 "흥!" 하는 츤데레 포즈(볼을 부풀리지 말기), 5) 사탕이 담긴 작은 바구니를 받아 들고 기뻐서 폴짝 뛰기, 6) 서서 하트 막대사탕 먹기, 7) 두 손으로 머리 위에 하트 모양 만들기, 8) 받은 선물 상자를 두 팔로 꼭 끌어안고 행복해하기.'}};
window.EVP=(name,kind,extra)=>{const e=EVK[kind];return '첨부한 그림은 이 캐릭터('+name+')의 바탕화면 데스크톱 펫 프레임이야. 이 캐릭터의 '+e.c+'를 한 장 만들어 줘. '+e.o+(extra?' '+extra:'')+' '+EVBASE(name)+' 칸 구성: '+e.k};
window.EVN=(name,kind,extra)=>{const e=EVK[kind];return '좋아. 같은 캐릭터('+name+')로 이번엔 '+e.c+'를 한 장 만들어 줘. 처음 첨부한 견본 그림의 얼굴·머리·그림체를 다시 기준으로 삼고, '+e.o+(extra?' '+extra:'')+' '+EVBASE(name)+' 칸 구성: '+e.k};
'ev ok';
// ── ChatGPT 탭 도우미 (위 프롬프트와 같이 붙여 넣기) ──
window.evimgs=()=>[...document.querySelectorAll('img')].filter(i=>i.naturalWidth>1500&&!i.closest('form')&&i.getBoundingClientRect().width>50);
window.evbusy=()=>!!document.querySelector('[data-testid="stop-button"],button[aria-label*="중지"],button[aria-label*="Stop"]');
window.evsend=(t)=>{document.querySelectorAll('img').forEach(i=>i.dataset.old=1);const e=[...document.querySelectorAll('div.ProseMirror')].filter(x=>x.getBoundingClientRect().width>0).at(-1);e.focus();document.execCommand('selectAll');document.execCommand('delete');document.execCommand('insertText',false,t);setTimeout(()=>{const b=[...document.querySelectorAll('button[aria-label="보내기"],[data-testid="send-button"],#composer-submit-button')].filter(b=>b.getBoundingClientRect().width>0).at(-1);b&&!b.disabled&&b.click()},1500);return 'sent'};
// 새 그림이 나올 때까지 (한 번에 최대 40초, 안 나오면 'wait' → 다시 부르기)
window.evwait=async(ms=40000)=>{const t0=Date.now();while(Date.now()-t0<ms){const n=evimgs().filter(i=>!i.dataset.old&&i.complete);if(n.length&&!evbusy())return 'ready '+n.at(-1).naturalWidth+'x'+n.at(-1).naturalHeight;await new Promise(r=>setTimeout(r,2000))}return 'wait busy:'+evbusy()};
// 원본 크기 그대로 4조각(q=0 왼위,1 오른위,2 왼아래,3 오른아래)으로 화면에 띄우기 → 각각 screenshot(scale 1, save_to_disk)
window.evtq=(q)=>{document.getElementById('__ov')?.remove();const im=evimgs().at(-1);const W=im.naturalWidth,H=im.naturalHeight;const ox=q%2?Math.max(0,W-innerWidth):0,oy=q>1?Math.max(0,H-innerHeight):0;const d=document.createElement('div');d.id='__ov';d.style.cssText='position:fixed;inset:0;z-index:2147483647;background:#0f0;overflow:hidden';const c=document.createElement('img');c.src=im.src;c.style.cssText='position:absolute;left:'+(-ox)+'px;top:'+(-oy)+'px;width:'+W+'px;height:'+H+'px;max-width:none;max-height:none';d.appendChild(c);document.body.appendChild(d);return W+'x'+H+' OFF '+ox+':'+oy};
window.evun=()=>{document.getElementById('__ov')?.remove();return 'ok'};
'ev ok';
