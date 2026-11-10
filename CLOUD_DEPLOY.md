# ERarchive 클라우드 배포 안내

이 안내는 서버 한 대에서 운영하는 모바일 경량 버전 기준입니다. SQLite DB, 계정, 일정, 홍보물 원본, 설정과 로그인 서명 키가 모두 `/app/data`에 저장됩니다. 컨테이너 이미지에는 기존 `data/`가 들어가지 않습니다. 반드시 **서버를 시작하기 전에** 영구 볼륨을 `/app/data`에 연결하세요. 이미지에 포함된 실행 설정은 이 경로가 마운트되지 않으면 빈 저장소를 만들지 않고 종료합니다.

**공개 전 확인:** 현재 앱은 로그인하지 않은 방문자도 Reader로 일정과 게시된 홍보물·규정을 볼 수 있습니다. HTTPS와 관리자 암호만으로 팀원 외 열람을 제한할 수 없습니다. 민감한 자료라면 공개 URL을 배포하기 전에 Cloudflare Access 같은 별도 접근 인증 또는 사설 VPN을 구성하고 원본 서버 주소로 우회할 수 없도록 제한하세요. Reader 로그인은 현재 열람의 필수 조건이 아닙니다. 기존 일반 열람 IP 제한은 프록시(Caddy/Railway) 뒤에서 실제 접속자 IP가 아닌 프록시 IP를 볼 수 있으므로 외부 접근 보호 수단으로 사용하지 마세요.

영구 볼륨은 재시작과 일반적인 재배포에서 파일을 보존하지만, 볼륨 삭제·계정 해지·장애·잘못된 작업까지 막지는 못합니다. 아래 백업을 정기적으로 수행하고 복구 가능 여부를 확인하세요. **SQLite와 파일 저장소를 공유하는 앱 인스턴스는 반드시 하나만 실행**하세요. 여러 복제본 또는 여러 서버에서 같은 폴더를 동시에 쓰지 마세요. 볼륨은 앱과 같은 리전에 두고 충분한 여유 용량을 확보하세요.

## 1. Railway로 배포

Railway의 화면 이름과 요금제는 변경될 수 있습니다. 영구 볼륨을 지원하는 요금제와 GitHub 계정이 필요합니다. 사용량과 볼륨 비용을 확인하세요.

1. 프로젝트의 변경사항을 검토해 GitHub **비공개 저장소**에 올립니다. `.gitignore`의 `data/`를 해제하지 말고 DB, 원본 파일, 암호, `secret.key`를 Git에 올리지 마세요.
2. Railway에서 새 프로젝트를 만들고 **Deploy from GitHub repo**로 저장소를 선택합니다. 루트의 `Dockerfile`과 `railway.json`이 사용됩니다. 첫 배포가 볼륨 미연결로 실패해도 정상입니다.
3. 앱 서비스에 Volume을 추가하고 마운트 경로를 정확히 `/app/data`로 지정합니다. 앱의 인스턴스/복제본 수는 **1개**로 유지합니다. 기존 볼륨을 삭제하거나 새 볼륨으로 바꾸지 마세요.
4. 서비스의 Variables에서 다음 값을 설정합니다.
   - `ERARCHIVE_DATA_DIR=/app/data`
   - `ERARCHIVE_REQUIRE_VOLUME=1`
   - `COOKIE_SECURE=1`
   - `ERARCHIVE_ADMIN_USER`: 최초 관리자 아이디. 영문·숫자·`_`·`-`, 2~40자
   - `ERARCHIVE_ADMIN_PASSWORD`: 최초 관리자 암호. 12~128자 이상의 길고 고유한 암호
   - `LAW_API_OC`: 국가법령정보센터에서 법령 원문을 가져올 때만 발급받은 OC 값

   `PORT`는 Railway가 주입합니다. 초기 관리자 환경변수는 **기존 관리자가 없을 때 한 번만** 계정을 만들며 기존 암호를 바꾸지 않습니다. 같은 이름의 Reader가 이미 있으면 중단되므로 다른 이름을 사용하세요.
5. 변경사항을 배포하거나 실패한 배포를 다시 실행합니다. 서비스 로그가 정상 실행 상태인지, `/healthz`가 `ok`인지 확인합니다. 서비스 설정의 Networking에서 도메인을 생성하면 Railway가 HTTPS를 제공합니다. 해당 HTTPS 주소로 접속해 관리자 로그인을 확인하세요.
6. 로그인 확인 후 `ERARCHIVE_ADMIN_USER`와 `ERARCHIVE_ADMIN_PASSWORD`를 Variables에서 **삭제하고 재배포**합니다. 계정은 볼륨의 DB에 남습니다. 브라우저에서 홍보물과 일정을 하나 등록하고 재배포 후 남아 있는지 확인하세요. 확인용 자료는 관리자 화면에서 삭제할 수 있습니다.
7. 사용 중인 Railway 공개 도메인과 사용자 지정 도메인 모두에 접근 제한을 적용하고, 제한을 우회하는 도메인이 외부에 남지 않도록 확인합니다. HTTPS는 전송 암호화이지 방문자 인증이 아닙니다.

이미 운영하던 데이터가 있다면 **새 빈 볼륨에 초기 계정을 만들기 전에** 기존 서버를 중지하고 `data/` 전체를 백업하여 새 볼륨에 복사해야 합니다. `archive.db`뿐 아니라 `images/`, `secret.key`, 기타 하위 폴더 및 남아 있는 SQLite `-wal`/`-shm` 파일도 빠짐없이 보존하세요. Railway의 볼륨 접근·복원 방법은 서비스에서 제공하는 현재 절차를 따르고, 복사 후 파일 수와 로그인·자료 열람을 확인하세요. 기존 DB에 관리자가 있으면 초기 관리자 변수를 설정할 필요가 없습니다.

## 2. 클라우드 VPS + Docker Compose + Caddy

Ubuntu 서버, 서버 공인 IP를 가리키는 도메인, 서버 SSH 접속 권한이 필요합니다. 아래 명령은 VPS의 터미널에서 실행합니다. Docker Engine과 Compose 플러그인은 [Docker 공식 Ubuntu 설치 안내](https://docs.docker.com/engine/install/ubuntu/)에 따라 설치하세요. `docker compose version`이 실행되어야 합니다.

1. 서버 방화벽과 클라우드 보안 그룹에서 TCP 80/443을 열고, SSH(22)는 관리자에게만 허용합니다. 앱 포트 8000은 인터넷에 열지 않습니다. DNS에서 예시 도메인 `archive.example.com`의 A 레코드를 VPS 공인 IP로 설정합니다.
2. GitHub의 저장소를 서버에 복제합니다. 비공개 저장소는 GitHub의 SSH 키 또는 액세스 설정이 필요합니다.

   ```bash
   git clone <본인-저장소-주소> erarchive
   cd erarchive
   mkdir -p data
   ```

   기존 자료를 이전한다면 서버를 중지한 기존 `data/`의 **전체 내용**을 이 `data/`에 먼저 복사합니다. 빈 폴더로 기존 자료를 덮어쓰지 마세요.
3. 새 데이터 폴더라면 이미지를 빌드하고 초기 관리자 계정을 만듭니다. 명령이 암호를 두 번 물으면 12자 이상을 입력합니다. 기존 관리자 계정을 옮겼다면 계정 생성 명령은 건너뜁니다.

   ```bash
   docker compose build
   docker compose run --rm erarchive python app.py --user admin --role admin
   docker compose up -d
   docker compose ps
   curl -fsS http://127.0.0.1:8000/healthz
   ```

   `ok`가 나오면 앱이 실행 중입니다. `docker compose run`에는 반드시 `--rm`을 사용합니다. 기본 설정은 서버 자신만 `127.0.0.1:8000`에 접속할 수 있게 합니다. API 검색을 사용하려면 서버 셸에서 `LAW_API_OC` 환경변수를 설정하고 `docker compose up -d`로 컨테이너를 다시 만드세요.
4. [Caddy 공식 설치 안내](https://caddyserver.com/docs/install)에 따라 Caddy를 설치한 후 `/etc/caddy/Caddyfile`을 편집합니다. 아래 도메인을 실제 소유 도메인으로 바꾸세요.

   ```caddyfile
   archive.example.com {
       reverse_proxy 127.0.0.1:8000
   }
   ```

   ```bash
   sudo caddy validate --config /etc/caddy/Caddyfile
   sudo systemctl enable --now caddy
   sudo systemctl reload caddy
   ```

   DNS가 올바르고 80/443이 외부에서 도달 가능하면 Caddy가 인증서를 자동 발급·갱신합니다. `https://archive.example.com`에서 로그인과 자료 등록을 확인합니다. 팀 외 접근을 막으려면 앞서 설명한 별도 접근 인증과 원본 서버 우회 차단을 추가해야 합니다.
5. 이후 코드 업데이트는 같은 폴더에서 다음과 같이 실행합니다. `data/`는 이미지에 포함되지 않고 계속 마운트됩니다. 작업 전에 백업하세요.

   ```bash
   git pull
   docker compose up -d --build
   docker compose ps
   ```

## 백업과 복구

볼륨은 백업이 아닙니다. Railway에서는 제공되는 볼륨 스냅샷/백업 정책을 설정하고, 별도 위치에도 복사본을 보관하세요. 삭제 및 복구 기능과 보존 기간은 사용 요금제를 확인하세요. 복구 연습을 하기 전에는 스냅샷의 유효성을 가정하지 마세요.

VPS에서는 일관된 백업을 위해 먼저 앱을 중지하고 **data 전체**를 묶습니다. 백업 파일은 서버 외부의 안전한 저장소로 복사하세요. `data`에 원본 파일과 계정 정보가 있으므로 백업도 비공개로 보호해야 합니다.

```bash
docker compose stop erarchive
sudo tar -C data -czf "../erarchive-backup-$(date +%Y%m%d-%H%M%S).tar.gz" .
docker compose start erarchive
```

복구할 때는 앱을 중지하고 현재 데이터를 별도 위치에 보존한 뒤, 백업을 **빈** `data/`에 풀고 다시 시작합니다. 복구 대상과 백업을 혼동하지 않도록 경로를 먼저 확인하세요. DB만 따로 복사하거나 실행 중인 SQLite 파일만 복사하면 업로드 파일·트랜잭션 상태와 일치하지 않을 수 있습니다. `docker compose down -v`, 볼륨 삭제, 저장소 삭제를 데이터 삭제 가능 작업으로 취급하세요.

## 경로와 실행 설정

- `ERARCHIVE_DATA_DIR` 미설정 시 기존 `ARCHIVE_DATA`를 지원하고, 둘 다 없으면 프로젝트의 `data/`를 사용합니다. 둘 다 있으면 `ERARCHIVE_DATA_DIR`이 우선합니다. 기존 `backup.py`에도 같은 우선순위가 적용됩니다.
- `PORT` 미설정 시 8000, 바인딩 주소는 `0.0.0.0`입니다. 기존 실행 스크립트처럼 `--host`와 `--port`로 명시적으로 바꿀 수 있습니다.
- Waitress가 운영용 HTTP 서버입니다. HTTPS는 Railway 또는 Caddy가 종료합니다. `COOKIE_SECURE=1`일 때 관리자 로그인은 HTTPS에서 사용하세요.
- `ERARCHIVE_REQUIRE_VOLUME=1`은 Linux 컨테이너에서 데이터 디렉터리가 마운트 지점인지 검사합니다. 마운트된 새 빈 볼륨의 오선택이나 볼륨 삭제는 감지하지 못합니다.

## 이 버전의 사용 범위

업로드한 2026-11-10 버전의 일정 줄바꿈과 법령·사규 전문 열람을 유지합니다. 자동 OCR/VL, 파일 수집폴더 감시와 문서에서 일정 자동 추출은 비활성화되어 있습니다. 관리자는 일정 폼으로 직접 등록하고 홍보물은 이미지/PDF와 제목·발행처 등을 입력하여 게시합니다. 기존 OCR 결과, 미처리 대기열과 원본 파일은 삭제하지 않습니다. 이전 자동 처리 대기열은 자동 재처리되지 않습니다. 원문 검색에 필요한 텍스트는 관리자가 직접 입력할 수 있습니다.

법령 API 검색과 관리자가 법령 원문을 가져와 확인한 뒤 저장하는 기존 기능을 제공합니다. `LAW_API_OC` 설정 또는 관리자 화면의 API 설정이 필요하며, 실제 서비스 이용에는 발급 상태와 외부 네트워크 연결이 필요합니다. 뉴스·재무·경조사 코드는 보존하지만 주요 모바일 탭에서 숨깁니다. PDF는 브라우저의 내장 뷰어로 열며, 브라우저에 따라 원본 열기 버튼이 필요할 수 있습니다. 오프라인 캐시는 제공하지 않습니다.
