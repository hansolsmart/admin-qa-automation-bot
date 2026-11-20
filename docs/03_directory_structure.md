# STEP 03 디렉터리 구조와 모듈 경계

아래 구조는 구현 목표다. 현재 추가하지 않은 파일은 각 산출물의 해당 STEP에서 생성한다.

```text
app/
  main.py               앱 생성, 라우터 및 미들웨어 등록
  config.py             환경 설정과 입력 검증
  database.py           엔진, 연결 설정, 세션
  models.py             SQLAlchemy 모델
  schemas.py            API 요청·응답 모델
  routers/              auth, items, runs, pages
  services/             인증, 등록 멱등성, 실행·결과 정책
  repositories/         DB 읽기·쓰기와 원자적 작업 점유
  templates/            로그인, 관리 항목, QA 대시보드
  static/               화면 동작 및 스타일
qa/
  conftest.py            격리 DB·테스트 앱·브라우저·결과 수집
  test_normal.py         정상 시나리오 3종
  test_network.py        응답 단절·재시도
  test_special.py        특수문자 원문 보존
  test_duplicate.py      중복 제출과 동시성
tests/                  API·DB·Worker 검증
worker/                 작업 점유 및 pytest 하위 프로세스 관리
alembic/                마이그레이션 이력
docs/                   단계별 기획·검증·운영 문서
reports/                로컬 실행의 로그·스크린샷·결과 (기본 Git 제외)
scripts/                계정 초기화·백업·복원 등 운영 명령
.github/workflows/       QA와 이미지 빌드 검증
.env.example             환경 변수 샘플
requirements.txt         고정 Python 의존성
pytest.ini               자동화 실행 경계와 설정
alembic.ini              마이그레이션 설정
Dockerfile               앱 및 Worker 실행 환경
compose.yaml             앱·Worker·공유 볼륨
README.md                설치·실행·테스트 명령
```

## 인터페이스

| 호출자 → 대상 | 처리 계약 |
| --- | --- |
| UI → Router | JSON API와 동일 출처 세션 쿠키. 상태 변경에 CSRF 헤더 적용 |
| Router → Service | 인증된 관리자 식별자와 검증된 DTO 전달. 도메인 오류를 HTTP 응답으로 매핑 |
| Service → Repository | 서비스가 트랜잭션 경계 결정. 저장소는 전달받은 세션에서 조회·갱신 |
| Worker → Repository | 실행 ID와 점유 토큰 기준으로 heartbeat 및 종료 처리. 지난 점유의 결과는 반영 거부 |
| Worker → pytest | 시나리오 ID를 고정 목록의 테스트 식별자로 변환. 환경 변수로 실행 ID·전용 DB·증거 디렉터리 전달 |
| pytest → Worker | 시나리오별 판정과 기간, 근거 메시지, 증거 상대 경로 반환. 수집·형식 오류는 실행 실패로 처리 |

의존성 방향은 `UI → Router → Service → Repository → DB`다. Worker는 웹 라우터에 의존하지 않고 저장소 및 결과 수집 서비스만 재사용한다. DB·API의 구체 필드와 오류 코드는 STEP 04~07에서 확정한다.

## 검증 기록

2026-11-19 `python -`으로 구조 검사 실행. 초기 검사의 노드 추출식이 라벨이 붙은 노드를 빠뜨렸고, 시퀀스에 DB 커밋 응답이 생략되어 있었다. 추출식을 보완하고 커밋 응답을 명시한 뒤 컴포넌트 연결, 참여자 연결, 작업 순서, 디렉터리 목록, 데이터 격리 계약을 재확인했다. 5개 통과, 실패 0개. Mermaid 렌더링과 앱 통합은 이 검사 범위에 포함되지 않는다.
