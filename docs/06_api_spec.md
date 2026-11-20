# STEP 06 API 명세

같은 출처에서 JSON API를 제공한다. 로그인은 JSON 요청만 받는다. `세션+CSRF`는 `admin_qa_session` 쿠키와 로그인 또는 `/api/auth/me`가 발행한 토큰의 `X-CSRF-Token` 헤더를 요구한다.

| Method | 경로 | 권한 | 요청 및 검증 | 성공 응답 | 업무 오류 |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/auth/login` | 공개 | `username`, `password` 문자열 | 200 `{username, csrf_token}`, 세션 쿠키 | 401 `INVALID_CREDENTIALS`, 429 `LOGIN_LIMITED` |
| POST | `/api/auth/logout` | 세션+CSRF | 본문 없음 | 204, 쿠키 만료 | 401, 403 |
| GET | `/api/auth/me` | 세션 | 없음 | 200 `{username, csrf_token}` | 401 |
| GET | `/api/items` | 세션 | `before` 양수 ID, `limit` 1~100, 기본 25 | 200 `{items, next_before}` | 401, 422 |
| POST | `/api/items` | 세션+CSRF | `Idempotency-Key` 1~128자 영숫자 및 `._-`, `name` 1~100자, `description` 0~500자 | 201 최초 응답, 200 재생 응답. `{id, name, description, created_at, updated_at}` | 401, 403, 409 `IDEMPOTENCY_CONFLICT`, 422, 503 |
| PATCH | `/api/items/{id}` | 세션+CSRF | 양수 ID, `name`·`description` 중 하나 이상, null 금지 | 200 갱신된 항목 | 401, 403, 404 `ITEM_NOT_FOUND`, 422, 503 |
| POST | `/api/qa/runs` | 세션+CSRF | `scenarios`에 허용 ID 1~6개, 중복 금지 | 202 `{id, status}` | 401, 403, 422, 503 |
| GET | `/api/qa/runs` | 세션 | `before`, `limit` | 200 `{runs, next_before, metrics}` | 401, 422 |
| GET | `/api/qa/runs/{id}` | 세션 | 양수 ID | 200 실행 상세 및 개별 결과 배열 | 401, 404 `RUN_NOT_FOUND` |
| GET | `/api/qa/runs/{id}/evidence/{artifact}` | 세션 | `log` 또는 선택된 시나리오 ID | 200 첨부 파일 | 401, 404 `EVIDENCE_NOT_FOUND` |
| GET | `/health` | 공개 | 없음 | 200 `{status: "ok"}` | 503 `DB_UNAVAILABLE` |

목록은 `id DESC` 순서와 다음 커서를 반환한다. 실행 상세는 `id`, `status`, `scenarios`, `requested_at`, `started_at`, `finished_at`, `error_code`, `log_url`, `results`를 포함한다. 결과 요소는 `scenario_id`, `status`, `duration_ms`, `detail`, `screenshot_url`을 제공한다. 목록 `metrics`는 완료 실행의 전체 판정을 집계한다.

오류는 `{error: {code, message}, request_id}` 구조로 반환한다. 공통 오류 코드는 `UNAUTHENTICATED`, `CSRF_REJECTED`, `VALIDATION_ERROR`, `DB_BUSY`, `DB_UNAVAILABLE`이다. 모든 응답에 `X-Request-ID`를 포함한다. 검증 오류에 입력 원문과 비밀번호를 포함하지 않는다.
