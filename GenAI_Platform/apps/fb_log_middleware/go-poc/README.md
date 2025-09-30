(임시)
# 준비
kubectl get secrets -n efk
이후 elasticsearch-...-crt 확인, 맨 위 ca.crt 내용 base64 decode하여 ./server 내에 이동

# 실행
go run server.go

# k8s
docker build --tag=192.168.1.14:30500/jfb/fb_log_middleware:0.1.0 . \
&& docker push 192.168.1.14:30500/jfb/fb_log_middleware:0.1.0 \
&& kubectl delete pod -n efk log-middleware-
# tab으로 log-middleware 이름 자동완성

# 테스트
curl --location --request POST http://localhost:32715/v1/dashboard/admin --data-raw '{"timespan": "15m","count": 10, "offset": 0}'
# nodeport 등은 확인