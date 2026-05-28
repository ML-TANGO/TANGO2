# FE Install & Build
FROM node:20 as build-stage
WORKDIR /app
COPY . .
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN rm -rf node_modules .yarn
RUN yarn install --frozen-lockfile
RUN yarn build


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
