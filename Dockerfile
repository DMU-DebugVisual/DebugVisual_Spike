name: Build & Deploy Spike (GHCR → EC2)

on:
  push:
    branches: [ main ]

permissions:
  contents: read
  packages: write  # GHCR 푸시 권한

jobs:
  build-push-deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # 🔥 루트의 Dockerfile(네가 준 것)로 빌드합니다.
      - name: Build & Push spike image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: |
            ghcr.io/dmu-debugvisual/debugvisual-spike:latest
            ghcr.io/dmu-debugvisual/debugvisual-spike:${{ github.sha }}

      # 선택: EC2에 바로 배포 (Secrets: EC2_HOST / EC2_USER / EC2_KEY 필요)
      - name: Deploy on EC2 (compose pull/up)
        env:
          HOST: ${{ secrets.EC2_HOST }}
          USER: ${{ secrets.EC2_USER }}
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.EC2_KEY }}" > ~/.ssh/id_rsa
          # 윈도우 개행 방지
          sed -i 's/\r$//' ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan -H "$HOST" >> ~/.ssh/known_hosts
          ssh "$USER@$HOST" "\
            docker login ghcr.io -u ${{ github.actor }} -p ${{ secrets.GITHUB_TOKEN }} && \
            cd ~/apps/debugvisual && \
            docker compose pull && \
            docker compose up -d && \
            docker image prune -af || true"
