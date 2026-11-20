# Admin QA Automation Bot

관리자가 항목을 등록·조회·수정하고, QA 대시보드에서 Playwright 시나리오를 실행하는 로컬 앱입니다. FastAPI와 SQLite가 관리 데이터 및 QA 이력을 보관하고, 별도 Worker가 각 테스트를 전용 DB와 loopback 앱에서 실행합니다.

## Windows에서 실행

프로젝트 루트에서 Python 3.14 가상 환경을 준비합니다. 아래 브라우저 설정은 설치된 Chrome을 사용합니다. Playwright 번들 Chromium을 쓰려면 `python -m playwright install chromium`을 실행하고 브라우저 채널 설정을 생략합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.bootstrap create-admin local-admin
.\.venv\Scripts\python.exe -m app.bootstrap serve
```

두 번째 터미널에서 Worker를 실행합니다.

```powershell
$env:ADMIN_QA_BROWSER_CHANNEL = 'chrome'
.\.venv\Scripts\python.exe -m worker
```

[관리자 화면](http://127.0.0.1:8000/)에서 만든 계정으로 로그인합니다. 데이터 관리에서 저장 결과를 확인하고, QA 대시보드에서 시나리오를 선택해 실행합니다. 실행 상세에서 판정·로그·스크린샷을 확인할 수 있습니다.

## 로컬 검증

```powershell
$env:ADMIN_QA_BROWSER_CHANNEL = 'chrome'
$env:QA_OUTPUT_DIR = 'reports/local'
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/local/junit.xml
.\.venv\Scripts\python.exe -m scripts.benchmark reports/local-benchmark
```

- [단계별 검증 기록](docs/verification_log.md)
- [장애 재현·복구 결과](docs/15_incident_report.md)
- [로컬 운영 Runbook](docs/16_runbook.md)
- [최종 결과 보고서](docs/16_final_report.md)

## Docker Compose

Docker 환경에서 공유 이미지를 빌드한 뒤 로컬 앱과 Worker를 실행합니다.

```text
docker compose build app
docker compose up -d --wait
docker compose exec app python -m app.bootstrap create-admin local-admin
```

이 프로젝트의 검증 환경에서는 Docker와 원격 CI 실행이 미확인 상태입니다. Windows 네이티브 실행과 검증 결과는 최종 보고서에 있습니다.
