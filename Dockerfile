FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ERARCHIVE_DATA_DIR=/app/data \
    ERARCHIVE_REQUIRE_VOLUME=1 \
    ERARCHIVE_DISABLE_FOLDER_WATCHERS=1 \
    PORT=8000
WORKDIR /app
COPY requirements.txt ./
# Optional build secret supports private proxies without baking certificates into the image.
RUN --mount=type=secret,id=pip_ca \
    if [ -s /run/secrets/pip_ca ]; then PIP_CERT=/run/secrets/pip_ca pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
