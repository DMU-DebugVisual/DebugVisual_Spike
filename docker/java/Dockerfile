FROM openjdk:17-jdk-slim
WORKDIR /usr/src/app

COPY entrypoint.sh /usr/src/app/entrypoint.sh

RUN chmod +x /usr/src/app/entrypoint.sh

CMD ["bash", "/usr/src/app/entrypoint.sh"]