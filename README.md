# 🎮 HRD Clan Bot

배틀그라운드에서 함께 플레이할 팀원을 구하는 디스코드 봇입니다.

## 📋 기능

- **구인 양식 설정**: 게임 시간과 게임 종류를 선택
- **구인 시작**: @here 태그와 함께 구인 메시지 발송
- **참여/취소**: 버튼을 클릭하여 참여 가능
- **데이터 저장**: 봇 재시작 후에도 참여 정보 유지

## 🚀 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/pafq202/HRD_Clan_Bot.git
cd HRD_Clan_Bot
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 설정
`.env` 파일을 생성하고 다음을 추가하세요:
```
DISCORD_TOKEN=YOUR_BOT_TOKEN_HERE
```

### 4. 봇 실행
```bash
python main.py
```

## 📖 사용 방법

### 명령어

#### `.구인 양식`
게임 시간과 게임 종류를 선택하는 창을 표시합니다.

**선택 옵션:**
- **게임 시간**: 미정, 모일시 바로 시작, 오후 1시, 오후 3시, 오후 6시, 오후 9시, 밤 11시
- **게임 종류**: 미정, 일반, 경쟁, 미니게임, 커스텀

#### `.구인 시작`
선택한 설정으로 구인 메시지를 @here 태그와 함께 발송합니다.

**메시지에 포함되는 정보:**
- 🎮 BATTLEGROUND @here
- 게임 시간
- 게임 종류
- 참여 인원 (1~4명)
- 참여 / 참여취소 버튼

## 📁 프로젝트 구조

```
HRD_Clan_Bot/
├── main.py                           # 봇 시작 파일
├── requirements.txt                  # 필요 패키지
├── .env                              # 환경 설정 (토큰)
├── .gitignore                        # git 제외 파일
├── README.md                         # 프로젝트 설명
│
├── config/
│   ├── __init__.py
│   ├── config.py                     # 설정 파일
│   ├── config.ini                    # 봇 설정 (색상 등)
│   └── comment.ini                   # 메시지 문구
│
├── cogs/
│   ├── __init__.py
│   └── recruitment.py                # 구인 관련 기능
│
├── utils/
│   ├── __init__.py
│   └── directory.py                  # 경로 관리 유틸리티
│
└── data/
    └── pending_recruitment.json      # 구인 데이터 (자동 생성)
```

## 🔧 설정 파일

### config.ini

봇의 기본 설정 파일입니다.

```ini
[Default]
token = YOUR_BOT_TOKEN_HERE
color = 0000FF
channels = []

[DelayDelete]
pending_recruitment = 30
```

### comment.ini

봇에서 사용하는 모든 메시지 문구입니다.

## ⚠️ 주의사항

- `.env` 파일은 절대 GitHub에 올리지 마세요 (토큰 노출 위험)
- 봇을 초대할 때 다음 권한이 필요합니다:
  - 메시지 읽기
  - 메시지 작성
  - 메시지 관리
  - 반응 추가
  - 음성 채널 접근

## 📝 라이센스

GNU General Public License v3.0

## 👨‍💻 개발

- **원본**: gunyu1019/recruitment-bot
- **수정**: pafq202

## 🐛 버그 리포트

문제를 발견하면 [Issues](https://github.com/pafq202/HRD_Clan_Bot/issues)에 등록해주세요.
