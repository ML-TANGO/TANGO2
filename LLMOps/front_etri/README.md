# Jonathan Flightbase

분할된 플베

## installation

```dotenv
# .env
VITE_REACT_APP_MODE="dev"
VITE_REACT_APP_API_HOST="local"
VITE_REACT_APP_MARKER_API_HOST="http://localhost:9999/"
VITE_REACT_APP_MARKER_API_URL="fix"
VITE_REACT_APP_ANALYTICS_TOKEN="UA-177651624-1"
VITE_REACT_APP_IS_MARKER="true"
VITE_REACT_APP_MARKER_VERSION="2"
VITE_REACT_APP_IS_INTELLIGENCE="true"
VITE_REACT_APP_IS_TOOL_RSTUDIO="true"
VITE_REACT_APP_IS_TOOL_FILEBROWSER="true"
VITE_REACT_APP_GOOGLE_API_KEY="<YOUR_GOOGLE_API_KEY>"
VITE_REACT_APP_GOOGLE_CLIENT_ID="<YOUR_GOOGLE_OAUTH_CLIENT_ID>.apps.googleusercontent.com"
VITE_REACT_APP_UPDATE_DATE="2024.09.01"
```

로컬에선 이렇게 사용한다

## How to Build

아래 과정은 빌드 서버에서 진행 (예시 — 실제 빌드 환경에 맞춰 조정).

### Dockerfile

```shell
# ./Dockerfile
# FE Install & Build
FROM node:20 as build-stage
WORKDIR /app
COPY . .
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

```

`Dockerfile`을 만든다

### nginx setting

```shell
# ./default.conf
server {
  listen 8001;
  server_name 0.0.0.0;

  location / {
       proxy_connect_timeout 3600;
       proxy_read_timeout 3600;
       proxy_send_timeout 3600;
       send_timeout 3600;
       root   /app/build;
       try_files $uri /index.html;
       index  index.html index.htm;
  }
}
```

### env setting

```dotenv
# .env
VITE_REACT_APP_MODE="dev"
VITE_REACT_APP_API_HOST="local"
VITE_REACT_APP_MARKER_API_HOST="http://localhost:9999/"
VITE_REACT_APP_MARKER_API_URL="custom"
VITE_REACT_APP_ANALYTICS_TOKEN="UA-177651624-1"
VITE_REACT_APP_IS_MARKER="true"
VITE_REACT_APP_MARKER_VERSION="2"
VITE_REACT_APP_IS_INTELLIGENCE="true"
VITE_REACT_APP_IS_TOOL_RSTUDIO="true"
VITE_REACT_APP_IS_TOOL_FILEBROWSER="true"
VITE_REACT_APP_GOOGLE_API_KEY="<YOUR_GOOGLE_API_KEY>"
VITE_REACT_APP_GOOGLE_CLIENT_ID="<YOUR_GOOGLE_OAUTH_CLIENT_ID>.apps.googleusercontent.com"
VITE_REACT_APP_UPDATE_DATE="2024.09.01"
```

### build & deploying

```shell
docker build -t <REGISTRY>/<NAMESPACE>/fb-front-dev:<TAG> -f Dockerfile .
docker push <REGISTRY>/<NAMESPACE>/fb-front-dev:<TAG>
docker save -o fb_front_0_1.tar <REGISTRY>/<NAMESPACE>/fb-front-dev:<TAG>  # Docker Image tar 파일

```

## API

- Swagger: http://&lt;API_HOST&gt;:9123/api/#docs
