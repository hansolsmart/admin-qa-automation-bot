# STEP 04 데이터 사전

시각 값은 UTC Unix 초이며, 생성·만료 관련 시각은 애플리케이션에서 명시적으로 기록한다. 표에서 `—`는 기본값 없음이다. 사용자 텍스트 제한은 유니코드 코드 포인트 기준이다. NUL 문자와 비어 있는 이름은 API 검증에서 거부한다.

| 테이블 | 필드 | 타입 | NULL | 기본값 | 규칙·용도 |
| --- | --- | --- | --- | --- | --- |
| admin_users | id | INTEGER | 불가 | 자동 정수 PK | 관리자 식별자 |
| admin_users | username | TEXT | 불가 | — | UNIQUE, 정규화한 로그인 ID 1~64자 |
| admin_users | password_hash | TEXT | 불가 | — | salt 포함 해시 문자열 |
| admin_users | failed_login_count | INTEGER | 불가 | 0 | 0 이상 |
| admin_users | login_locked_until | INTEGER | 허용 | NULL | 계정 잠금 종료 |
| admin_users | created_at | INTEGER | 불가 | — | 계정 생성 |
| admin_sessions | token_hash | TEXT | 불가 | — | PK, 64자 토큰 해시 |
| admin_sessions | admin_id | INTEGER | 불가 | — | `admin_users.id` 참조 |
| admin_sessions | created_at | INTEGER | 불가 | — | 세션 발급 |
| admin_sessions | expires_at | INTEGER | 불가 | — | 발급 시각 이후 만료 |
| admin_items | id | INTEGER | 불가 | 자동 정수 PK | 항목 식별자 |
| admin_items | created_by | INTEGER | 불가 | — | `admin_users.id` 참조 |
| admin_items | name | TEXT | 불가 | — | 1~100자, 원문 보존 |
| admin_items | description | TEXT | 불가 | 빈 문자열 | 0~500자, 원문 보존 |
| admin_items | created_at | INTEGER | 불가 | — | 최초 등록 |
| admin_items | updated_at | INTEGER | 불가 | — | 마지막 수정 또는 등록 |
| idempotency_records | id | INTEGER | 불가 | 자동 정수 PK | 등록 기록 식별자 |
| idempotency_records | admin_id | INTEGER | 불가 | — | `admin_users.id` 참조, 키 범위 |
| idempotency_records | item_id | INTEGER | 불가 | — | UNIQUE, `admin_items.id` 참조 |
| idempotency_records | idempotency_key | TEXT | 불가 | — | 1~128자, 관리자 ID와 복합 UNIQUE |
| idempotency_records | request_hash | TEXT | 불가 | — | 정규화한 요청 본문의 64자 해시 |
| idempotency_records | response_json | TEXT | 불가 | — | 최초 등록 결과 JSON 객체 |
| idempotency_records | created_at | INTEGER | 불가 | — | 최초 성공 기록 시각 |
| qa_runs | id | INTEGER | 불가 | 자동 정수 PK | 실행 식별자 |
| qa_runs | requested_by | INTEGER | 불가 | — | `admin_users.id` 참조 |
| qa_runs | selected_scenarios | TEXT | 불가 | — | 고정 ID 1~6개가 포함된 JSON 배열 |
| qa_runs | status | TEXT | 불가 | PENDING | PENDING, RUNNING, COMPLETED, FAILED |
| qa_runs | requested_at | INTEGER | 불가 | — | 요청 접수 |
| qa_runs | started_at | INTEGER | 허용 | NULL | Worker 점유 |
| qa_runs | heartbeat_at | INTEGER | 허용 | NULL | 마지막 점유 갱신 |
| qa_runs | lease_token | TEXT | 허용 | NULL | RUNNING 상태에서 점유 식별 |
| qa_runs | lease_expires_at | INTEGER | 허용 | NULL | RUNNING 상태에서 점유 만료 |
| qa_runs | finished_at | INTEGER | 허용 | NULL | 종료 상태 기록 |
| qa_runs | error_code | TEXT | 허용 | NULL | FAILED의 원인 코드 |
| qa_runs | log_path | TEXT | 허용 | NULL | 보고서 루트 아래 로그 상대 경로 |
| qa_results | id | INTEGER | 불가 | 자동 정수 PK | 결과 식별자 |
| qa_results | run_id | INTEGER | 불가 | — | `qa_runs.id` 참조 |
| qa_results | scenario_id | TEXT | 불가 | — | 고정 시나리오 ID, `run_id`와 복합 UNIQUE |
| qa_results | status | TEXT | 불가 | — | PASS, FAIL, ERROR, SKIPPED |
| qa_results | duration_ms | INTEGER | 불가 | — | 0 이상, 소요 시간(밀리초) |
| qa_results | detail | TEXT | 허용 | NULL | 민감정보를 제거한 판정 근거 |
| qa_results | screenshot_path | TEXT | 허용 | NULL | 보고서 루트 아래 스크린샷 상대 경로 |

## 관계와 조회 키

- 실행 대기열은 `(status, id)`, 만료 조회는 `(status, lease_expires_at)` 인덱스로 지원한다.
- 항목·실행 목록은 `id DESC` 기준 커서 조회. 실행 상세의 개별 판정은 `(run_id, scenario_id)` 인덱스로 조회한다.
- 계정·항목·실행은 MVP API에서 삭제하지 않는다. 세션은 로그아웃 시 삭제하며, 만료 세션의 정리는 운영 정책으로 관리한다. 멱등성 기록은 항목과 함께 보존한다.

## 검증 기록

2026-11-19 `python -`으로 ERD와 데이터 사전 대조. 최초 검사에서 기대 필드 수를 잘못 입력해 `qa_runs`의 실제 필드 수 12개와 전체 42개로 수정했다. ERD 3단계, 엔터티 6개, 필드 42개, PK·FK 참조, 복합키, 상태 집합 검사를 재실행해 6개 통과, 실패 0개. 실제 스키마 일치와 무결성은 STEP 05에서 검증한다.
