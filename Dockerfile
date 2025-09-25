FROM python:3.9-slim-bookworm

WORKDIR /usr/src/app

# Python 서버 파일 복사
COPY server/app.py .
COPY server/code ./code

# requirements.txt 복사 → 꼭 있어야 함
COPY requirements.txt ./

# 모든 언어의 entrypoint 스크립트 복사
COPY docker/python/entrypoint.sh ./entrypoint_python.sh
COPY docker/java/entrypoint.sh   ./entrypoint_java.sh
COPY docker/c/entrypoint.sh      ./entrypoint_c.sh

# 실행 권한 부여
RUN chmod +x entrypoint_*.sh

# 필요한 Python 패키지 설치 (Flask + OpenAI + dotenv 등 전부)
RUN pip install --no-cache-dir -r requirements.txt

# 필요한 패키지 설치 전 캐시 클리어
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io && \
    ln -s /usr/bin/docker /usr/local/bin/docker && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Python 버퍼링 비활성화
ENV PYTHONUNBUFFERED=1

EXPOSE 5050

CMD ["python", "-Xutf8", "app.py"]
