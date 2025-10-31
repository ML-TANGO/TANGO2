#!/bin/bash
echo "============"
echo "yarn install"
echo "============"
cd /front-data
yarn install

echo "=========="
echo "yarn build"
echo "=========="
yarn build-pack:all

# ================================================================================
echo "============="
echo "Edit Setting "
echo "============="

# config-real에서 VITE_REACT_APP_API_HOST 값이 없어야 현재 페이지를 기준으로 API 호출함
### 2023-12-18 luke VITE_REACT_APP_API_HOST 선언 자체가 되어 있지 않아야 프론트에서 현재 기준으로 API_HOST 세팅함
### .env.real에서 아예 선언하지 않던가 프론트 로직 수정 필요
sed "s|api-url||g; s|marker-url|$protocol_config://$marker_url/|g" /front-data/install/flight-base/config-real > .env.real
mv -f .env.real /front-data/apps/flightbase/configs/app-config/vite-env/.env.real

sed "s|faviconItem|$favicon_item|g; s|titleItem|$title_item|g" /front-data/install/flight-base/index.html > index.html
mv -f index.html /front-data/apps/flightbase/public/
# ================================================================================

echo "=============="
echo "yarn workspace"
echo "=============="
cd /front-data
yarn workspace @jonathan/flightbase build:real


echo "==========================="
echo "FINISH JONATHAN FRONT BUILD"
echo "==========================="