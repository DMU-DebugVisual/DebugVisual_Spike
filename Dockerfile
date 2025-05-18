FROM python:3.9

WORKDIR /usr/src/app

# Python 서버 파일 복사
COPY server/app.py .
COPY server/code ./code

# 모든 언어의 entrypoint 스크립트 복사
COPY docker/python/entrypoint.sh ./entrypoint_python.sh
COPY docker/java/entrypoint.sh   ./entrypoint_java.sh
COPY docker/c/entrypoint.sh      ./entrypoint_c.sh

# 실행 권한 부여
RUN chmod +x entrypoint_*.sh

# Flask 설치
RUN pip install flask

EXPOSE 5050

CMD ["python", "app.py"]
