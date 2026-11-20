# STEP 16 로컬 운영 Runbook

## 시작과 상태 확인

1. [README](../README.md)의 의존성 설치와 계정 생성 후 앱·Worker를 각각 실행한다.
2. `Invoke-RestMethod http://127.0.0.1:8000/health`가 `status=ok`를 반환하는지 확인한다.
3. 관리자 로그인 → QA 대시보드 → 시나리오 선택 → QA 실행 순서로 점검한다.
4. `PENDING → RUNNING → COMPLETED`와 테스트별 판정을 확인한다. 실행 로그는 `reports/run-<id>-<token>/worker.log`, 브라우저 증거는 같은 폴더에 저장한다.

| 설정 | 기본값 또는 용도 |
| --- | --- |
| `ADMIN_QA_DB_PATH` | `data/admin_qa.sqlite3`. 앱과 Worker에서 같은 값 사용 |
| `ADMIN_QA_REPORT_DIR` | `reports`. 앱과 Worker에서 같은 값 사용 |
| `ADMIN_QA_BROWSER_CHANNEL` | 생략 시 Playwright 번들 Chromium. 설치 Chrome은 `chrome` |
| `ADMIN_QA_SECURE_COOKIE` | 로컬 HTTP에서 생략. TLS를 갖춘 환경에서 `1` |
| `ADMIN_QA_PASSWORD` | 비대화식 계정 초기화용. CLI는 생략 시 숨김 입력 프롬프트 사용 |

## 실행 실패 처리

| 관측 증상 | 확인과 조치 |
| --- | --- |
| `PENDING` 유지 | Worker 실행 여부와 두 프로세스의 `ADMIN_QA_DB_PATH` 일치 확인 |
| `FAILED / LEASE_EXPIRED` | Worker 출력과 실행 이력 확인. Worker 재기동 후 새 실행으로 재검증 |
| `FAILED / TEST_TIMEOUT` 또는 `INVALID_RESULTS` | 실행 로그에서 브라우저 설치·권한과 테스트 결과 수집 확인 후 새 실행 |
| `COMPLETED`에 `FAIL` 포함 | 해당 시나리오의 판정 메시지, 화면, 로그 확인. 수정 후 같은 시나리오 실행 |
| 등록 응답 미확인 | 폼에 남은 같은 내용으로 다시 제출해 원래 등록 결과 확인 |
| `DB_BUSY` | 해당 Request ID의 요청 로그와 쓰기 작업 확인. 일시 대기 후 동일 키로 재시도 |

## 백업과 복원 검증

SQLite 백업 API로 WAL DB의 일관된 스냅샷을 새 경로에 만든다. `integrity_check`와 `foreign_key_check`가 성공한 파일을 사용한다. 스크린샷과 실행 로그를 보존하려면 같은 시점의 보고서 디렉터리도 함께 보관한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.db_snapshot data/admin_qa.sqlite3 data/backups/admin-01.sqlite3
.\.venv\Scripts\python.exe -m scripts.db_snapshot data/backups/admin-01.sqlite3 data/restore-check/admin.sqlite3
$env:ADMIN_QA_DB_PATH = 'data/restore-check/admin.sqlite3'
.\.venv\Scripts\python.exe -m alembic check
Remove-Item Env:ADMIN_QA_DB_PATH
```

검증한 복원 DB를 운영에 적용할 때는 앱과 Worker를 중지하고 두 프로세스가 같은 새 DB 경로를 사용하도록 설정한다. 스냅샷 명령은 기존 대상 파일의 덮어쓰기를 거부한다.
