# bookworm으로 핀 고정 (moving target 방지)
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /usr/src/app

# C/Java 컴파일러 설치 (gcc + JDK 17)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make openjdk-17-jdk-headless \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY server/app.py .
COPY server/code ./code
COPY docker/python/entrypoint.sh ./entrypoint_python.sh
COPY docker/java/entrypoint.sh   ./entrypoint_java.sh
RUN chmod +x entrypoint_*.sh

ENV PYTHONUNBUFFERED=1
EXPOSE 5050
CMD ["python", "-Xutf8", "app.py"]
