# STEP 10 인프라·CI 설계

Compose는 앱과 Worker에 같은 이미지를 사용한다. 앱은 마이그레이션 후 헬스 체크를 제공하고 Worker는 준비 이후 시작한다. 볼륨 `db_data`, `qa_reports`를 공유하며 예외 테스트용 DB는 Worker의 별도 임시 공간에 둔다. 호스트에는 loopback 앱 포트 하나를 열고 Worker 포트는 공개하지 않는다.

로컬과 CI는 `requirements.txt`의 Python 패키지와 Playwright 버전을 공유한다. Linux 이미지와 CI는 Playwright에 포함되는 Chromium 버전을 사용한다. Windows 로컬에서 설치된 Chrome을 쓰는 경우 브라우저 버전을 증거에 기록한다. 계정 비밀은 실행 환경에서 주입하거나 초기화 명령에서 직접 입력한다.

CI는 lint → 마이그레이션 검사 → API·Worker 검증 → Playwright → Docker/Compose 순서로 실행하고 실패 시 보고서를 보존한다. 승인 필요한 외부 배포 작업은 포함하지 않는다. Compose의 실제 빌드·기동과 GitHub Actions 실행 결과는 해당 환경에서 확인할 대상으로 관리한다.
