# STEP 05 SQLite 상세 설계

[데이터 사전](04_data_dictionary.md)의 6개 테이블을 SQLAlchemy로 정의하고, Alembic 초기 리비전으로 적용한다. DB 기본 경로는 `data/admin_qa.sqlite3`이며 `ADMIN_QA_DB_PATH`로 분리할 수 있다. 운영용과 QA 실행 전용 DB에는 같은 여섯 테이블이 생성된다.

| 테이블 | 제약과 인덱스 | 보존 및 참조 정책 |
| --- | --- | --- |
| `admin_users` | PK, 로그인 ID 유일성 및 길이, 실패 횟수 0 이상 | MVP 계정 삭제 API 제외, 하위 업무 기록이 있으면 삭제 제한 |
| `admin_sessions` | 토큰 해시 PK, 발급 이후 만료, 관리자와 만료 시각 인덱스 | 로그아웃 시 폐기. 소유 관리자 삭제 시 함께 정리 |
| `admin_items` | 이름·설명 길이 및 NUL 금지, 시각 순서, 작성자 인덱스 | 관리자 FK `RESTRICT`. 삭제 API 제외 |
| `idempotency_records` | `(admin_id, idempotency_key)` UNIQUE, `item_id` UNIQUE, 최초 응답 JSON 객체 | 관리자·항목 FK `RESTRICT`. 동일 등록 의도의 재시도를 위해 항목과 함께 보존 |
| `qa_runs` | 선택 JSON 배열 1~6개, 실행 상태별 가용 필드 제약, 대기·만료·요청자 인덱스 | 요청자 FK `RESTRICT`. 앱에서 실행 이력 삭제 기능 제외 |
| `qa_results` | `(run_id, scenario_id)` UNIQUE, 허용 시나리오·판정, 기간 0 이상 | 실행에 종속. 운영 보존 정책에서 실행 제거 시 함께 삭제 |

## 트랜잭션과 연결 정책

- 연결별 FK 활성화, 파일 DB의 WAL 모드, `busy_timeout` 5초. DB 파일과 WAL은 같은 로컬 파일시스템에 둔다.
- 등록과 멱등성 기록은 동일 트랜잭션. 멱등성 조회·등록 흐름의 쓰기 경쟁은 등록 서비스에서 짧은 `BEGIN IMMEDIATE`로 직렬화한다.
- 실행 상태와 결과 판정에 별도 제약 적용. 선택 배열의 허용 값·유일성과 판정의 선택 배열 포함 여부는 애플리케이션이 검증한다. 결과의 일괄 적재와 종료 상태 변경은 같은 트랜잭션에서 처리한다.
- QA 실행별 DB는 환경 설정 또는 마이그레이션 호출 시 경로를 명시해 생성한다. 이력 DB를 재사용하는 테스트 픽스처는 제외한다.
- 스키마 변경은 Alembic 리비전으로 적용한다. 모델·마이그레이션 차이는 `python -m alembic check`로 점검한다. 서비스 DB에 대한 강등은 백업과 승인 후 수행한다.

## 검증 기록

2026-11-19 Windows, Python 3.14.6의 프로젝트 가상 환경에서 `python -m pytest -q tests/test_database.py --tb=short` 실행. 6개 통과, 실패 0개. 마이그레이션 적용·재적용·모델 차이 검사·강등 후 재적용, FK·WAL·timeout, 입력 및 세션 제약, 중복 키 롤백, 상태·판정 제약, 파일 DB 격리를 확인했다. `python -m alembic upgrade head --sql`로 초기 스키마 SQL 출력도 확인했다.

최초 실행에서 테스트 1개가 상태 외에 시작 시각 제약도 동시에 위반했다. 테스트 입력에 정상 시작 시각을 주어 목표 제약 하나만 검증하도록 수정한 뒤 전체 DB 테스트를 다시 실행했다. 검증 코드는 `tests/test_database.py`에 있다. 실제 API 동시 요청과 Worker 격리는 STEP 14~15의 통합 테스트 대상이다.
