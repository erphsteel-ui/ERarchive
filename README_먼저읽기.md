# ER 아카이브 실행 안내

- 최초 설치: `01_setup_windows.bat`를 실행합니다.
- 본인 PC에서만 실행: `02_start_local.bat`를 실행한 뒤 안내된 주소를 엽니다.
- 사내망 팀원과 함께 사용: `03_start_team.bat`를 실행하고 서버 PC의 사내 IP와 8080 포트로 접속합니다. 실행 창은 열어 둡니다.
- 사용자 추가: `04_add_reader.bat`를 사용합니다.
- 백업: 서버를 종료한 후 `05_backup.bat`를 실행합니다.

기존 환경을 업데이트할 때는 서버를 종료하고 데이터를 백업한 다음 프로그램 파일을 덮어쓰세요. 기존 `data`, `.venv`, OCR 모델과 수집 폴더는 삭제하지 마세요. Windows 실행 스크립트는 기본적으로 `%LOCALAPPDATA%\ERArchive\data`를 사용합니다.

법령 API 설정은 `LAW_API_설정안내.md`, 자동 수집은 `자동수집_사용안내.md`를 참고하세요.
