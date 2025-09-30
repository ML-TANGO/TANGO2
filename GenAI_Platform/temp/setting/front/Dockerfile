FROM node:16.20.2-buster
RUN apt-get update && apt-get install -y nginx \
    vim curl wget net-tools python3 sudo openssl \
    build-essential libssl-dev make git-core

# build context 주의

# TODO -> /jfbcore/jf-bin/https-ssl.crt 부분 어떻게 처리할지,,,
# COPY jfbcore /jfbcore

COPY front/jonathan-platform-front /front-data
COPY front/init.sh /setting/

# ENV (불필요한 것들 확인 후 제거)
ENV marker_url "dev.marker.acryl.ai"
ENV favicon_item "favicon.ico"
ENV title_item "JONATHAN"
ENV protocol_config "http"
# ENV front_ip "0.0.0.0"
# ENV api_ip ""
# ENV api_port "56789"
# ENV api_call_port "56789"
# ENV branch "master"
# ENV front_build_config "default"
# ENV ui_guide "false"
# ENV project_path "/front-data/apps/flightbase/build"
# ENV nginx_listen_config ""
# ENV error_path "/front-data/apps/flightbase"
# ENV ui_style_path "/front-data/packages/ui/ui-style/dist"
# ENV ui_graph_path "/front-data/packages/ui/ui-graph/dist"
# ENV ui_react_path "/front-data/packages/ui/ui-react/storybook-static"

# build
WORKDIR /setting
RUN ./init.sh

# run
WORKDIR /front-data/apps/flightbase/configs/app-config/vite-env
CMD yarn run start:real \
    --port 8001; \
    while true; do sleep 30; done;