# STEP 11 관측성

| 기록 위치 | 기본 필드 | 용도 |
| --- | --- | --- |
| 웹 프로세스 stdout | 시간, 이벤트, Request ID, method, route, status, duration_ms, error_code | API 지연 및 오류 확인 |
| Worker stdout | 시간, 이벤트, Run ID, 상태, 오류 코드 | 점유·종료·복구 이력 |
| 실행별 `worker.log`와 `results.json` | Run ID, Scenario ID, 판정, 소요 시간, 증거 참조 | 개별 테스트 근거 확인 |

요청마다 서버에서 새 Request ID를 발급한다. QA 실행 응답의 ID를 요청 로그와 연결한다. 화면에서 시작 시각·완료 시각·상태·판정을 제공한다. 로그와 화면에서 자격 증명, 쿠키, 토큰, 요청 본문을 제외한다. 스크린샷에는 합성 테스트 데이터만 포함한다.
