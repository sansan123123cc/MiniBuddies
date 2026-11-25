# MiniBuddies 애니메이션 플러그인

MiniBuddies 폴더의 `plugins/<팩-id>/`에 `plugin.json`과 그림을 넣고 앱을 다시 실행하세요. 팩 ID는 소문자 영문·숫자로 시작하는 폴더 이름입니다. 펫을 우클릭해 **캐릭터 이름이 붙은 놀이 메뉴 → 플러그인 → 플러그인 폴더 열기**로 폴더를 만들 수 있습니다.

같은 메뉴에서 팩 이름을 펼쳐 **이 캐릭터에 연결**을 선택하세요. 메뉴를 다시 열면 연결한 캐릭터에서 행동을 실행할 수 있습니다. 연결은 `settings.json`에 캐릭터별로 저장되며, 같은 캐릭터의 여러 펫과 의상에 적용됩니다.

예를 들어 아래 JSON을 `plugins/tea-break/plugin.json`으로 저장하고 같은 폴더에 `frames/tea.png`, `frames/sip.png`를 넣을 수 있습니다.

```json
{
  "version": 1,
  "name": "차 한 잔",
  "characters": ["reimu", "marisa"],
  "actions": [
    {
      "name": "차 마시기",
      "say": "후우… 따뜻하다.",
      "idle_chance": 0.08,
      "frames": [
        {"file": "frames/tea.png", "ticks": 24},
        {"file": "frames/sip.png", "ticks": 38},
        {"file": "frames/tea.png", "ticks": 16}
      ]
    }
  ]
}
```

- 그림은 투명 배경 256×256 PNG를 사용합니다. 품질을 위해 발이나 접지 부분을 프레임 간 비슷하게 맞춰 주세요. 앱은 보이는 픽셀의 하단을 기준으로 그림을 배치합니다.
- `characters`는 연결할 수 있는 캐릭터의 `chars/` 폴더 이름입니다. 생략하거나 빈 배열로 두면 모든 캐릭터에 연결할 수 있습니다.
- `ticks` 1은 약 16ms입니다. `say`를 생략하면 말풍선 없이 재생합니다.
- `idle_chance`는 펫이 대기를 마치고 다음 행동을 고르는 시점에 이 행동을 시작할 확률입니다. 생략하면 메뉴에서만 실행됩니다.
- 잘못된 팩은 건너뛰고 `crash.log`에 이유를 남깁니다. 파일을 수정하거나 제거한 뒤 앱을 다시 시작하세요.

현재 팩 형식은 한 펫의 애니메이션과 말풍선을 지원합니다. 여러 펫이 함께하는 내장 놀이는 `minibuddies/features/`에서 관리합니다.

## 개발 파일 위치

- `buddies.py`는 기존 실행 진입점이고, `minibuddies/app.py`는 앱 상태와 펫 간 상호작용을 조율합니다.
- `minibuddies/pet.py`는 개별 펫의 상태, 이동, 프레임 재생을 담당합니다. 캐릭터 데이터는 `minibuddies/catalog.py`에 있습니다.
- `minibuddies/ui/`에는 설정창, 우클릭 메뉴, 화면 위 위젯이 있습니다.
- `minibuddies/features/touhou.py`에는 가드 타워와 탄막 로직이 있습니다. `features/legacy.py`는 기존 날씨·계절·변신 효과의 연결을 담당합니다.
- `minibuddies/plugins.py`는 팩을 읽고 연결과 재생을 처리합니다. `python -m unittest discover -s tests`로 연결과 재생을 검증할 수 있습니다.

배포용 manifest는 배포 시 모듈 경로를 포함해 다시 생성해야 합니다. Android 내보내기가 `buddies.py`에서 캐릭터 데이터를 읽는다면 입력을 새 데이터 모듈에 맞춰야 합니다.
