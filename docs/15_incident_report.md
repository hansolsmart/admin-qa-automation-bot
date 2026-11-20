# STEP 15 장애 재현·복구 보고서

2026-11-20 Windows, Python 3.14.6, Playwright 1.58.0, Chrome 157.0.8103.79에서 검증했다. 각 테스트는 합성 데이터와 전용 SQLite를 사용했다. 결함 프로필은 pytest에서 활성화하며, 서비스 Worker는 고정된 정상 프로필로 테스트를 시작한다.

| 장애 | 결함 조건 및 관측 결과 | 원인과 복구 결과 | 로컬 Git 태그 |
| --- | --- | --- | --- |
| BUG-01 등록 응답 단절 | 서버가 첫 등록을 201로 커밋한 뒤 Playwright가 브라우저 응답을 끊음. 재시도에 새 키를 쓰는 결함 프로필에서 201 재발급, 저장 2건, `FAIL` | 첫 응답이 유실되면 원래 요청의 결과를 브라우저가 알 수 없음. 본문과 키를 유지해 재시도하자 200, 최초 ID 및 저장 1건 확인, `PASS` | `bug-01-before` `4e4078e01d` / `bug-01-after` `80eae4a934` |
| BUG-02 특수문자 원문 손실 | 합성 한글·따옴표·앰퍼샌드·꺾쇠·SQL 단어 입력. 저장 전 꺾쇠를 제거하면 응답·DB·화면 원문이 모두 불일치, `FAIL` | 저장 전에 원문을 변형하는 처리로 값 손실. 원문 저장·파라미터 바인딩·화면 텍스트 표시 적용 후 세 지점 일치, `PASS` | `bug-02-before` `2e8fcfeb6a` / `bug-02-after` `ed5da9efc1` |
| BUG-03 빠른 클릭 및 동시 제출 | 브라우저 버튼 10회 호출 후 동일 키로 동시 HTTP 요청 10건. 서버가 요청마다 새 키를 쓰는 결함 프로필에서 201 10개, 서로 다른 ID와 저장 10건, `FAIL` | 원래 등록 의도를 식별하는 키가 서버에서 유지되지 않음. 버튼 제출 제한과 DB 트랜잭션 멱등성 적용 후 201 1개·200 9개, 단일 ID·저장 1건. 키 충돌 409와 독립 키 등록까지 확인, `PASS` | `bug-03-before` `806b4e0c27` / `bug-03-after` `7229982170` |

## 확인 방법과 증거

같은 테스트 파일과 입력으로 결함 상태와 복구 상태를 각각 실행했다. 두 태그의 변경은 테스트 전용 `qa/fault_profile.txt`이며 같은 앱 코드에서 재현 경로를 고른다. 여섯 태그를 각각 `git archive`로 독립 임시 폴더에 풀어, 환경 변수로 결함 조건을 덮어쓰지 않은 상태에서도 3개 기대 실패와 3개 통과를 다시 확인했다.

- 케이스별 `reports/step15/bug-0{1,2,3}/{before,after}/`에 pytest 로그, JUnit XML, JSON 판정, 스크린샷 기록.
- 로컬 태그 재실행 결과는 `reports/step15/tag_verification.json`. 스크린샷과 로그는 `reports/step15/tag-verify/`.
- 전체 회귀는 `python -m pytest -q --tb=short`로 22개 통과. `reports/step15/regression/`에 로그와 JUnit XML 기록.

같은 조건을 현재 브랜치에서 다시 실행하려면 PowerShell의 `QA_DEMO_FAULT`에 `network`, `special`, `duplicate` 중 하나를 지정하고 해당 테스트 파일을 실행한다. 복구는 같은 명령에 `fixed`를 지정한다. 아래는 BUG-01 실행 예시다.

```powershell
$env:ADMIN_QA_BROWSER_CHANNEL = 'chrome'
$env:QA_DEMO_FAULT = 'network'
$env:QA_OUTPUT_DIR = 'reports/replay/bug-01-before'
.\.venv\Scripts\python.exe -m pytest qa/test_network.py -q -s
$env:QA_DEMO_FAULT = 'fixed'
$env:QA_OUTPUT_DIR = 'reports/replay/bug-01-after'
.\.venv\Scripts\python.exe -m pytest qa/test_network.py -q -s
Remove-Item Env:QA_DEMO_FAULT
```
