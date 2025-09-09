# ✅ 최신 LTS 기반 (debian bookworm)
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /usr/src/app

# 1) 시스템 패키지 (C/Java 컴파일용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make openjdk-17-jdk-headless \
 && rm -rf /var/lib/apt/lists/*

# 2) 파이썬 의존성
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 3) 앱 코드/스크립트
COPY server/app.py .
COPY server/code ./code
COPY docker/python/entrypoint.sh ./entrypoint_python.sh
COPY docker/java/entrypoint.sh   ./entrypoint_java.sh
# (C 스크립트가 있다면 추가) COPY docker/c/entrypoint.sh ./entrypoint_c.sh
RUN chmod +x entrypoint_*.sh

# 4) 런타임 설정
ENV PYTHONUNBUFFERED=1
EXPOSE 5050
CMD ["python", "-Xutf8", "app.py"]
