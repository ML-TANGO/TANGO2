### 사전준비
``` shell
brew install k6
```

### 테스트 방법
``` shell
k6 run --env KEYCLOAK_CLIENT_SECRET=YOUR_SECRET_HERE test/send.js
```
