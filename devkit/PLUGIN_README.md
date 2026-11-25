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
- `characters`는 연결할 수 있는 캐릭터의 `chars/` 폴더 이름입니다. 생략하거나 빈 배열로 두면 개별 동작은 모든 캐릭터에게 연결할 수 있습니다. 상호작용만 들어 있는 팩은 지정된 참가자에게만 표시됩니다.
- `ticks` 1은 약 16ms입니다. `say`를 생략하면 말풍선 없이 재생합니다.
- `idle_chance`는 펫이 대기를 마치고 다음 행동을 고르는 시점에 이 행동을 시작할 확률입니다. 생략하면 메뉴에서만 실행됩니다.
- 잘못된 팩은 건너뛰고 `crash.log`에 이유를 남깁니다. 파일을 수정하거나 제거한 뒤 앱을 다시 시작하세요.

## 여러 캐릭터의 상호작용

`interactions`에 참여할 캐릭터와 시간순 동작을 넣을 수 있습니다. 참가자 모두에게 팩을 연결한 뒤 같은 모니터와 바닥에 가까이 두면 **같이 놀기 → 플러그인 상호작용**에서 실행됩니다.

```json
{
  "version": 1,
  "name": "별빛 교환",
  "interactions": [
    {
      "name": "레이무와 마리사의 탄막",
      "meet_chance": 0.12,
      "meet_distance": 340,
      "cooldown_seconds": 40,
      "roles": [
        {
          "character": "reimu",
          "steps": [
            {"ticks": 20, "frame": 200},
            {"ticks": 22, "frame": 201, "say": "먼저 할게!",
             "effect": {"preset": "seal", "target": "marisa", "colors": ["#ff7890", "#97c8fd"]}},
            {"ticks": 60, "frame": 0}
          ]
        },
        {
          "character": "marisa",
          "steps": [
            {"ticks": 42, "frame": 0},
            {"ticks": 22, "frame": 201, "say": "이번엔 나야!",
             "effect": {"preset": "spark", "target": "reimu", "colors": ["#cc93ff", "#ffdb68", "#fff7db"]}},
            {"ticks": 16, "frame": 202}
          ]
        }
      ]
    }
  ]
}
```

- 역할은 서로 다른 캐릭터 2~6명입니다. 각 역할의 `steps`가 동시에 시작하며, 각 단계의 `ticks`가 지난 뒤 다음 단계로 넘어갑니다.
- `frame`은 캐릭터에 내장된 PNG의 번호입니다. 팩에서 새 그림을 제공하려면 `frame` 자리에 `"file": "frames/my-cast.png"`를 사용하세요. 둘 다 생략하면 앞선 단계의 포즈를 유지합니다.
- `effect.preset`에는 `seal`, `spark`, `moon`, `fairy`, `freeze`, `petal`, `books`, `sun`, `clock`, `scarlet`, `slash`를 쓸 수 있습니다. `target`으로 상대를, `colors`로 색상을 정합니다. 효과의 `ticks` 기본값은 78이며 단계보다 길게 재생할 수 있습니다.
- `meet_chance`는 자동 놀이 검사 때의 발동 확률입니다. 생략하면 메뉴에서만 실행됩니다. `meet_distance`는 가장 멀리 떨어진 두 참가자 사이의 허용 거리이고, `cooldown_seconds`는 같은 놀이가 자동으로 다시 시작되기까지의 최소 시간입니다.
- 한 팩에 `actions`와 `interactions`를 함께 넣을 수 있습니다. 참여자를 집거나 화면에서 없애거나 팩 연결을 끊으면 진행 중인 놀이가 정리됩니다.

## 개발 파일 위치

- `buddies.py`는 기존 실행 진입점입니다. `minibuddies/app.py`는 앱을 초기화하고 `controllers/`의 캐릭터 관리, 단체 놀이, 데스크톱 연동, 배포 기능 등을 조합합니다.
- `minibuddies/pets/`는 개별 펫의 상태, 이동, 프레임 재생, 마우스 입력을 담당합니다. 캐릭터 데이터는 `minibuddies/catalog/`에 작품·그룹별로 들어 있습니다.
- `minibuddies/ui/`에는 설정창, 우클릭 메뉴, 화면 위 위젯이 있습니다. 설정 탭은 캐릭터, 화면, 놀이, 연동별로 나뉩니다.
- `minibuddies/features/`는 가드 타워·탄막, 날씨, 계절 의상, 변신 등 내장 특수 행동을 기능별로 담습니다. `install_builtin()`이 기존 실행 순서대로 연결합니다.
- `minibuddies/plugins/packs.py`와 `scenes.py`가 JSON·PNG를 검증합니다. `library.py`가 캐릭터별 연결과 개별 동작을, `interactions.py`가 여러 펫의 모임과 재생을 처리합니다. 내장 동방 탄막과 플러그인 탄막은 `minibuddies/effects.py`의 렌더러를 공유합니다.
- `python -m unittest discover -s tests`로 캐릭터 연결, 개별 재생, 두 펫의 상호작용과 정리를 검증할 수 있습니다.

배포용 manifest는 배포 시 모듈 경로를 포함해 다시 생성해야 합니다. Android 내보내기가 `buddies.py`에서 캐릭터 데이터를 읽는다면 입력을 `minibuddies/catalog/`에 맞춰야 합니다.
