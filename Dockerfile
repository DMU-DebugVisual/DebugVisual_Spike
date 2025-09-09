FROM python:3.9-slim-buster

WORKDIR /usr/src/app

# 의존성 먼저 설치 (캐시 활용)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY server/app.py .
COPY server/code ./code

# 엔트리포인트 스크립트 복사
COPY docker/python/entrypoint.sh ./entrypoint_python.sh
COPY docker/java/entrypoint.sh   ./entrypoint_java.sh
RUN chmod +x entrypoint_*.sh

# Python 버퍼링 비활성화
ENV PYTHONUNBUFFERED=1

EXPOSE 5050

CMD ["python", "-Xutf8", "app.py"]
