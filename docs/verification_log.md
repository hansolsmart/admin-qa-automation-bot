# 단계별 검증 기록

| 단계 | 실제 확인 결과 | 실측 또는 실행 대기 |
| --- | --- | --- |
| 06 | `python -` 명세 검사에서 API 11개·업무 규칙 9개 및 테스트 ID 연결 통과 | API 통합 STEP 14 |
| 07 | `python -`으로 결과 필드와 SQLAlchemy 모델 매핑 확인 | 수집·검증·집계 STEP 14 |
| 08 | `python -`으로 3개 화면, 명세 API 및 접근성 사례 연결 확인 | 키보드·모바일 브라우저 STEP 14 |
| 09 | `python -`으로 인증·세션·출력 보호 계약 및 보안 테스트 연결 확인 | 보안 테스트 STEP 14 |

2026-11-20 STEP 06~09 문서 검사 4개 통과. 별도 임시 Python 소켓으로 loopback 연결 검증 통과. 기존 DB 테스트 6개 통과. 런타임 검증은 진행 단계별로 아래에 추가한다.

| 단계 | 실제 확인 결과 | 증거 또는 남은 조건 |
| --- | --- | --- |
| 10 | 구성의 서비스 2개, loopback 포트, 헬스 체크, 볼륨, CI 검사 순서 확인. GitHub Actions의 Ubuntu 24.04에서 Docker 이미지 빌드 및 Compose 앱·Worker 기동 성공 | [GitHub Actions 실행 결과](https://github.com/hansolsmart/admin-qa-automation-bot/actions/runs/44662514077) |
| 11 | 상태 전이·heartbeat·시간 제한 명세 점검. STEP 14에서 4개 동시 점유 시 정확히 1개 성공, 만료 후 종료 쓰기 거부와 재실행 확인 | `tests/test_worker.py` |
| 12 | `pytest qa --collect-only`로 제품 시나리오 6개 확인. Playwright의 Chrome 157.0.8103.79 헤드리스 실행 확인 | 정상·예외 실제 판정은 STEP 14~15 |
| 13 | 조회·등록 각 40건, 동시성 4, p95·대기·메모리 등 부하 검증 기준 확인 | STEP 16 실측 |
| 14 | Windows/Python 3.14.6에서 DB·API·Worker 13개, 정상 Playwright 3개, Dashboard 및 모바일 2개 통과. Ruff와 JS 문법 검사 통과 | `reports/step14/{unit,normal,integration}/`의 로그·JUnit·화면 증거 |

STEP 10 초기 정적 검사에서 Compose 변수 비교식의 이스케이프를 수정했다. STEP 11 검사의 문서 경로도 수정하고 다시 실행했다. STEP 14 테스트에서 Starlette TestClient의 AnyIO 별칭 사용에 따른 의존성 deprecation 경고 1건이 발생했다. 테스트 실패는 0건이었다.

| 단계 | 실제 확인 결과 | 증거 또는 남은 조건 |
| --- | --- | --- |
| 15 | 케이스별 pytest로 기대 실패 3/3 및 복구 통과 3/3, Git 태그 6개에서 동일 판정, 전체 회귀 22개 통과 | [장애 보고서](15_incident_report.md), `reports/step15/` |
| 16 | 로컬 최종 회귀 22개, 대시보드의 정상·예외 6개, CLI 기동·백업·복원, 성능 기준 6개 통과. GitHub Actions에서 Python·Playwright 테스트 및 Docker Compose 기동 검증 통과. Vercel 소개 페이지 공개 검증 완료 | [최종 보고서](16_final_report.md) · [CI 실행 결과 및 로그](https://github.com/hansolsmart/admin-qa-automation-bot/actions/runs/44662514077) · [공개 포트폴리오](https://admin-qa-portfolio.vercel.app/) |
