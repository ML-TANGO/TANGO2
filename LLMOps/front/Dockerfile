# FE Install & Build
FROM node:20 as build-stage
WORKDIR /app
COPY . .
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN rm -rf node_modules .yarn
# yarn.lock 은 yarn 4(berry) 형식 — node:20 기본 yarn 1 로는 설치되지 않는다
RUN corepack enable && corepack prepare yarn@4.17.1 --activate
RUN yarn install --immutable
# yarn build 의 `rm -rf ./build/*` 는 berry 셸에서 빈 glob 이면 실패한다 — 깨끗한 컨테이너라 vite 만 돌린다
RUN yarn vite build


# 실행 스테이지
FROM nginx:latest AS runtime-stage


# Nginx 설정 복사
COPY --from=build-stage /app/default.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default


# 빌드된 애플리케이션 복사
COPY --from=build-stage /app/build /app/build


# Nginx 실행 스크립트 작성
RUN echo "#!/bin/bash" > /entrypoint.sh \
 && echo "nginx -g 'daemon off;' &" >> /entrypoint.sh \
 && echo "while true; do sleep 30; done;" >> /entrypoint.sh \
 && chmod +x /entrypoint.sh
