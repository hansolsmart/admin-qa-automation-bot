# STEP 16 MVP 최종 결과

2026-11-20 Windows에서 관리자 로그인·로그아웃, 항목 등록·조회·수정, 브라우저 QA 요청과 Worker 실행, 결과 집계·이력·증거 조회를 검증했다. 테스트에는 Python 3.14.6, SQLite 3.50.4, Playwright 1.58.0, Chrome 157.0.8103.79를 사용했다.

## 실행 검증

| 검증 | 결과 | 증거 |
| --- | --- | --- |
| 최종 회귀 | `python -m pytest -q --tb=short`로 22개 통과, 실패·건너뜀 0개. DB·API·Worker·운영 14개, 브라우저 8개 | 로컬 `reports/step16/final/{junit.xml,pytest.log}` |
| 대시보드 통합 | Worker를 거쳐 6개 시나리오 `PASS`, 집계 6건, 새로고침 뒤 이력·로그·스크린샷 조회 성공 | 로컬 `reports/step16/final/dashboard/dashboard.png` |
| 장애 재현·복구 | 기대 실패 3/3, 동일 테스트의 복구 통과 3/3, 분리한 소스에서 태그 6개 재실행 | [장애 보고서](15_incident_report.md) |
| 네이티브 앱 및 복원 | CLI 계정 생성, 앱 기동, 헬스 200, 로그인 200, 등록 201. 동작 중 DB 백업, 별도 경로 복원, 데이터와 스키마 확인 | 로컬 `reports/step16/native-smoke/result.json` |
| 정적 검사·의존성 | Ruff, `node --check app/static/app.js`, `pip check` 통과. Starlette TestClient에서 AnyIO deprecation 경고 1건 | 로컬 `reports/step16/final/{ruff.log,pytest.log}` |

## 로컬 성능 기준선

`python -m scripts.benchmark reports/step16/performance` 실행. 16개 논리 프로세서의 Windows 환경에서 Uvicorn 앱·Worker 각 1개와 SQLite WAL을 사용했다. 두 API 각 40건, 동시성 4, 중복 검증은 같은 키로 동시성 10이었다. p95는 클라이언트 왕복 시간의 nearest-rank 값이다. 대기·실행 시간은 DB 타임스탬프의 초 단위 차이다.

| 지표 | 실측 | 기준 |
| --- | --- | --- |
| 조회 p95 | 20.68 ms | < 500 ms |
| 등록 p95 | 63.77 ms | < 500 ms |
| `DB_BUSY`·중복 저장 | 각각 0건, 공유 키의 등록 행 1건 | 각각 0건 |
| 대기·정상 QA 3종 실행 | 0초·6초, 3/3 PASS | < 5초·< 120초 |
| Worker 최대 메모리 표본 | 본체 Working Set 3.88 MiB, 표본 10개 | 표본 기록. 브라우저·자식 프로세스 별도 |

성능 검사 6개를 통과했다. 이 부하 조건에서 목표를 넘긴 항목은 없었다. 장기 부하 및 최적화 전후 비교는 미측정이다. 원시 측정값은 로컬 `reports/step16/performance/benchmark.json`에 있다.

## GitHub Actions 및 공개 포트폴리오

2026-11-20 GitHub Actions의 Ubuntu 24.04 환경에서 코드 검사, DB 마이그레이션, Python 테스트, Playwright 브라우저 테스트를 통과했다. Docker 이미지 빌드와 `docker compose up -d --wait`가 성공해 앱과 QA Worker의 정상 기동을 확인했다. [CI 실행 결과 및 로그](https://github.com/hansolsmart/admin-qa-automation-bot/actions/runs/44662514077)

Vercel에 장애 3종의 실패·복구 결과, 실행 로그와 스크린샷을 담은 소개 페이지를 배포했다. 페이지와 증거 파일은 로그인 없이 접근할 수 있다. [공개 포트폴리오](https://admin-qa-portfolio.vercel.app/)

## 완료 상태

| 범위 | 상태 |
| --- | --- |
| 요구사항·설계·DB 마이그레이션 | 로컬 검증 완료 |
| API·인증·화면·Worker·QA 데이터 수집·대시보드 | 로컬 검증 완료 |
| 정상 3종, 장애 3종 재현·복구, 전체 회귀 | 로컬 검증 완료 |
| 네이티브 로컬 앱·백업·복원·성능 | 로컬 검증 완료 |
| Docker 이미지 빌드·Compose 구동 | GitHub Actions 환경에서 앱·Worker 기동 검증 완료 |
| GitHub Actions | 코드 검사·마이그레이션·Python·브라우저 테스트 통과 |
| 포트폴리오 공개 | Vercel 배포 및 로그인 없는 접근 확인 |
| 관리자 앱의 외부 실행 데모 | 범위 제외 |

운영 절차는 [Runbook](16_runbook.md), 단계별 상세는 [검증 기록](verification_log.md)에 있다. 원시 로그·JUnit·스크린샷은 로컬 `reports/`에 보존했다. GitHub에서 볼 수 있는 증거는 [README의 실행 #3](../README.md#qa-대시보드-실행-3)에 있다.
