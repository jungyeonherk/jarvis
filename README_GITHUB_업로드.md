# ☁️ J.A.R.V.I.S 클라우드 자동 스캐너 — GitHub 업로드 가이드

## 📋 GitHub에 올려야 할 파일 3개

| # | 파일명 | 위치 | 역할 |
|---|--------|------|------|
| 1 | `jarvis-v3.html` | 루트 → `index.html`로 변경 | 자비스 메인 (폰에서 열림) |
| 2 | `cloud_scanner.py` | 루트 | 매일 자동 실행되는 스캐너 |
| 3 | `daily_scan.yml` | `.github/workflows/` 폴더 | GitHub Actions 자동 스케줄 |

---

## 🚀 단계별 가이드 (총 15분)

### 1단계: 기존 파일 정리 (3분)

폰 크롬에서 https://github.com/jungyeonherk/jarvis 접속

기존 HTML 파일 모두 삭제 → README.md만 남기기

### 2단계: jarvis-v3.html을 index.html로 업로드 (3분)

1. **Add file** → **Upload files**
2. `jarvis-v3.html` 선택
3. ⚠️ **이름을 `index.html`로 변경 후 업로드** (URL 깔끔하게 만들기 위해)
4. **Commit changes** 클릭

### 3단계: cloud_scanner.py 업로드 (2분)

1. **Add file** → **Upload files**
2. `cloud_scanner.py` 그대로 업로드
3. **Commit changes** 클릭

### 4단계: GitHub Actions 워크플로우 업로드 (5분) ⭐ 가장 중요

⚠️ 이 파일은 **`.github/workflows/`** 라는 특별한 폴더에 들어가야 함

1. 저장소 메인 → **Add file** → **Create new file**
2. 파일명 입력란에 정확히 다음과 같이 타이핑:
   ```
   .github/workflows/daily_scan.yml
   ```
   (슬래시 `/`가 폴더를 자동 생성함)
3. 화면이 코드 편집기로 바뀌면 → `daily_scan.yml`의 **전체 내용 복사 후 붙여넣기**
4. 페이지 하단 **Commit changes**

### 5단계: 첫 수동 스캔 테스트 (5분)

1. 저장소 → 상단 **Actions** 탭
2. 좌측 **🔎 J.A.R.V.I.S Daily Scan** 클릭
3. 우측 **Run workflow** 버튼 → **Run workflow** (초록 버튼)
4. 30초 대기 후 새로고침 → 노란 점이 진행 중
5. **5-10분 후 초록 체크 ✓**

### 6단계: 결과 확인

1. 저장소 메인으로 → `docs/` 폴더 생겼는지 확인
2. `docs/scan_result.json` 파일 클릭 → 오늘 스캔 결과 보임
3. 자비스 접속: `https://jungyeonherk.github.io/jarvis/`
4. 부팅 시 검은 박스에 다음 메시지 보임:
   ```
   > ☁️ Cloud scan: 2026-04-27 (10 stocks)
   ```
5. ACTIVATE 후 **"클라우드"** 음성 명령 → 상태 확인

---

## 🤔 자주 묻는 질문

### Q1. 첫 자동 실행은 언제?
**다음 평일 한국시간 18:00**. 그 전엔 수동 실행으로 테스트.

### Q2. 한도/비용?
저장소가 **공개(Public)** 이면 완전 무료. 비공개면 월 2000분 무료.

### Q3. 스캔 결과가 안 좋으면?
첫 실행은 보통 5-7분 걸림. 10분 넘으면 Actions 탭에서 빨간 X 클릭해서 로그 확인.

### Q4. 키움 OpenAPI 같은 인증 필요?
**아니요.** pykrx + 네이버 금융 둘 다 무료/공개 데이터.

---

## 📊 작동 흐름

```
매일 18:00 KST (월~금)
   ↓
GitHub Actions 자동 시작 (Ubuntu 클라우드, 무료)
   ↓
cloud_scanner.py 실행
   ↓ KOSPI+KOSDAQ 약 1700-2000종목 가져옴
   ↓ 네이버 금융 → 시그널 ②③④⑤ 분석
   ↓ pykrx → 시그널 ① 공매도 분석
   ↓ 점수순 정렬 → TOP 10
   ↓
docs/scan_result.json 자동 푸시
   ↓
jungyeonherk.github.io/jarvis/docs/scan_result.json (공개 URL)
   ↓
보스 폰 자비스가 자동 fetch
   ↓
"오늘 종목" 음성 명령 → 새 결과 보고
```

---

## ✅ 성공 체크리스트

- [ ] index.html (자비스 v3) 업로드
- [ ] cloud_scanner.py 업로드
- [ ] .github/workflows/daily_scan.yml 업로드
- [ ] Actions 탭에서 첫 수동 실행 → ✓ 성공
- [ ] docs/scan_result.json 파일 생성됨
- [ ] 자비스 접속 시 부팅 화면에 ☁️ Cloud scan 메시지 보임
- [ ] "클라우드" 명령 → 상태 보고됨
