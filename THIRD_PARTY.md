# 포함 구성요소

Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, blinker, click, colorama, waitress, Pillow의 Windows Python 3.12 x64용 wheel을 포함합니다. 각 배포본의 라이선스는 wheel 안의 dist-info/licenses 또는 LICENSE 파일에 포함되어 있습니다. Python 및 Tesseract 엔진은 포함하지 않습니다.

examples의 이미지들은 사용자가 제공한 자료이며, 예시용 수동 메타데이터는 examples.json에 있습니다.

## 본문 OCR 모델

ocr-models/kor.traineddata, eng.traineddata: tesseract-ocr/tessdata_best, Apache License 2.0. 라이선스 전문은 ocr-models/LICENSE에 포함합니다.
출처: https://github.com/tesseract-ocr/tessdata_best (2026-10-21 다운로드)

kor.traineddata SHA256: f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff

eng.traineddata SHA256: 8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba


## HWP 본문 읽기 (v0.12)

vendor/olefile: olefile 0.47, BSD 2-Clause. 라이선스는 vendor/olefile/LICENSE.txt,
기여자 목록은 vendor/olefile/CONTRIBUTORS.txt에 포함합니다. 추가 pip 설치 없이 로컬에서 사용합니다.
업데이트 ZIP에는 Windows wheel, OCR 모델, 예시 이미지가 포함되지 않습니다.
