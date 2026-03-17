# Tango MSA 서비스 Docker 이미지 빌드 가이드

> 📌 **이 문서는 외부 협력 기관 개발자를 위한 Docker 이미지 빌드 가이드입니다.** Tango GenAI 플랫폼에 MSA 서비스를 탑재하려면 서비스를 Docker 이미지로 빌드하고 플랫폼이 접근 가능한 레지스트리에 등록해야 합니다.
> 

---

# 0. 시작하기 전에

## 0.1 이 문서의 목적

본 문서는 협력 기관 개발자가 자체 **MSA 서비스**를 Docker 이미지로 빌드하고, Tango GenAI 플랫폼에 탑재 가능한 형태로 준비하는 전 과정을 안내합니다.

<aside>
💡

**MSA(Microservice Architecture) 서비스란?**

하나의 거대한 프로그램 대신, 기능별로 잘게 나눈 독립적인 작은 서비스들의 모음입니다. 예를 들어 "AI 추론", "데이터 전처리", "결과 시각화" 같은 기능을 각각 별도의 서비스로 만들고, 이를 필요에 따라 조합해서 사용하는 방식입니다.
이 문서에서 말하는 'MSA 서비스'는 **여러분이 독립적으로 개발한 하나의 프론트-백엔드 묶음의 서비스 단위**를 의미합니다. 이 서비스를 Docker 이미지로 만들어 Tango 플랫폼 위에 올리면, 플랫폼의 GPU·네트워크·인증 인프라를 그대로 활용할 수 있게 됩니다.

</aside>

이미지 빌드를 완료한 이후의 Helm Chart 작성 및 배포 절차는 **Tango MSA 탑재 가이드**를 참고하세요.

## 0.2 대상 독자

- Tango 플랫폼에 처음으로 MSA 서비스를 탑재하려는 협력 기관 개발자
- 기존 서비스를 컨테이너화하여 플랫폼에 연동하려는 개발자

## 0.3 용어 정리

| 용어 | 설명 |
| --- | --- |
| **Docker 이미지** | 서비스 실행에 필요한 코드, 런타임, 라이브러리 등을 하나로 패키징한 실행 단위 |
| **Dockerfile** | Docker 이미지를 빌드하기 위한 명령어 모음 파일 |
| **컨테이너 레지스트리** | Docker 이미지를 저장하고 배포하는 저장소. 플랫폼이 이곳에서 이미지를 pull함 |
| **엔드포인트** | HTTP 요청을 받을 수 있는 URL 경로. 플랫폼이 서비스를 호출할 때 사용 |
| **Helm Chart** | 쿠버네티스에 서비스를 배포하기 위한 설정 패키지 |

## 0.4 사전 요건

- Docker가 로컬 환경에 설치되어 있어야 합니다
- 플랫폼 담당자로부터 컨테이너 레지스트리 주소 및 접근 정보를 안내받아야 합니다
- 서비스 코드(프론트엔드 또는 백엔드)가 준비되어 있어야 합니다

---

# 1. 개요

## 1.1 왜 Docker 이미지가 필요한가?

Tango GenAI 플랫폼은 쿠버네티스(Kubernetes) 기반으로 동작합니다. 쿠버네티스는 컨테이너 단위로 서비스를 배포·실행하기 때문에, 협력기관의 서비스를 **Docker 이미지로 패키징**하는 것이 필수입니다.

빌드된 이미지는 컨테이너 레지스트리에 업로드(Push)되고, Helm Chart의 `values.yaml`에서 이미지 경로를 참조하여 클러스터에 배포됩니다.

## 1.2 전체 흐름

MSA 서비스를 플랫폼에 탑재하기 위한 Docker 이미지 준비 과정은 아래 순서로 진행됩니다.

| 단계 | 내용 |
| --- | --- |
| **1단계** | 서비스 코드 준비 — 필수 API 엔드포인트 구현 포함 |
| **2단계** | Dockerfile 작성 — 프론트엔드 / 백엔드 각각 |
| **3단계** | Docker 이미지 빌드 |
| **4단계** | 레지스트리에 이미지 Push |
| **5단계** | Helm Chart의 `values.yaml`에 이미지 경로 등록 |

## 1.3 서비스 구성 유형

Tango 플랫폼에 탑재되는 MSA 서비스는 일반적으로 아래 두 가지 컴포넌트로 구성됩니다.

| 컴포넌트 | 설명 | 필수 여부 |
| --- | --- | --- |
| **백엔드** | 서비스의 핵심 로직 처리. 플랫폼의 API 호출을 직접 수신 | ✅ 필수 |
| **프론트엔드** | 사용자 UI 제공. 플랫폼 내에서 iframe 또는 별도 창으로 노출 | 선택 |

---

# 2. 필수 API 엔드포인트 구현

플랫폼이 서비스를 호출하기 위해 **백엔드에 아래 3개의 엔드포인트가 반드시 구현**되어 있어야 합니다. 이미지 빌드 전에 코드에 포함되어 있는지 반드시 확인하세요.

> 💡 각 엔드포인트의 상세 명세는 **Tango MSA 탑재 가이드 — 5장 API 인터페이스 명세**를 참고하세요.
> 

| 엔드포인트 | 메서드 | 설명 |
| --- | --- | --- |
| `/health` | GET | 서비스 정상 동작 여부 확인. 플랫폼이 주기적으로 호출 |
| `/info` | GET | 서비스 이름, 버전, 기능 목록 반환 |
| `/run` | POST | 서비스 핵심 기능 실행 (동기 방식) |

**Python(FastAPI) 구현 예시:**

```python
from fastapi import FastAPI
from datetime import datetime, timezone

app = FastAPI()

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/info")
def get_info():
    return {
        "name": "my-service",
        "version": "1.0.0",
        "description": "서비스 설명",
        "capabilities": ["feature_a"]
    }

@app.post("/run")
def run_service(body: dict):
    workspace_id = body.get("workspace_id")
    project_id = body.get("project_id")
    params = body.get("params", {})

    # 서비스 핵심 로직 실행
    result = your_core_logic(params)

    return {
        "status": "success",
        "result": result
    }
```

**Node.js(Express) 구현 예시:**

```jsx
const express = require('express');
const app = express();
app.use(express.json());

app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString()
  });
});

app.get('/info', (req, res) => {
  res.json({
    name: 'my-service',
    version: '1.0.0',
    description: '서비스 설명',
    capabilities: ['feature_a']
  });
});

app.post('/run', (req, res) => {
  const { workspace_id, project_id, params } = req.body;
  const result = yourCoreLogic(params);
  res.json({ status: 'success', result });
});

app.listen(30000);
```

---

# 3. 디렉토리 구조 및 파일 구성

이미지 빌드 전 서비스 디렉토리가 아래와 같이 구성되어 있어야 합니다.

**백엔드 예시 (Python):**

```
my-backend/
├── Dockerfile          ← 이미지 빌드 설정
├── requirements.txt    ← Python 의존성 목록
├── app.py              ← 서비스 진입점 (/health, /info, /run 포함)
└── src/
    └── ...             ← 서비스 핵심 로직
```

**프론트엔드 예시 (React/Nginx):**

```
my-frontend/
├── Dockerfile          ← 이미지 빌드 설정
├── nginx.conf          ← Nginx 설정 파일
├── package.json
├── public/
└── src/
    └── ...             ← UI 코드
```

---

# 4. Dockerfile 작성

## 4.1 백엔드 Dockerfile (Python 예시)

```docker
# 베이스 이미지 선택 (CUDA가 필요한 경우 nvidia/cuda 사용)
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 복사 후 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 서비스 코드 복사
COPY . .

# 서비스가 사용할 포트 노출
# values.yaml의 backend.port와 반드시 일치해야 함
EXPOSE 30000

# 서비스 실행 명령
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "30000"]
```

**GPU가 필요한 백엔드의 경우:**

```docker
# CUDA 환경이 필요한 경우 베이스 이미지 교체
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

RUN apt-get update && apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 30000
CMD ["python3", "app.py"]
```

## 4.2 프론트엔드 Dockerfile (React + Nginx 예시)

```docker
# 1단계: 빌드
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
RUN npm run build

# 2단계: Nginx로 서빙
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

# values.yaml의 service.frontend1.targetPort와 반드시 일치해야 함
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf 예시:**

```
events {}
http {
    include /etc/nginx/mime.types;
    server {
        listen 80;
        root /usr/share/nginx/html;
        index index.html;

        # React SPA 라우팅 지원
        location / {
            try_files $uri $uri/ /index.html;
        }

        # 백엔드 API 프록시 (필요한 경우)
        location /api/ {
            proxy_pass http://my-backend-svc:30000/;
        }
    }
}
```

> ⚠️ **포트 주의사항:** Dockerfile의 `EXPOSE` 포트는 Helm Chart `values.yaml`의 `targetPort`와 반드시 일치해야 합니다. 다를 경우 서비스가 정상적으로 노출되지 않습니다.
> 

## 4.3 .dockerignore

빌드 컨텍스트에 불필요한 파일이 포함되면 이미지 크기가 커지고 빌드 속도가 느려집니다. `.dockerignore` 파일을 작성하여 제외할 항목을 지정하세요.

```
__pycache__/
*.pyc
*.pyo
.git/
.env
.venv/
venv/
node_modules/
*.log
.DS_Store
```

> 💡 **팁:** 현재 개발 환경의 Python 패키지 목록을 자동으로 생성하려면 `pip freeze > requirements.txt` 명령을 사용하세요. 다만 불필요한 패키지가 포함될 수 있으므로, 서비스에 실제로 필요한 패키지만 남기는 것을 권장합니다.
> 

---

# 5. Docker 이미지 빌드

## 5.1 빌드 명령어

```bash
# 백엔드 이미지 빌드
docker build -t <레지스트리주소>/<이미지명>:<태그> ./my-backend

# 예시
docker build -t docker.io/my-org/my-service-backend:v1.0.0 ./my-backend

# 프론트엔드 이미지 빌드
docker build -t docker.io/my-org/my-service-frontend:v1.0.0 ./my-frontend
```

## 5.2 빌드 확인

```bash
# 빌드된 이미지 목록 확인
docker images | grep my-service

# 로컬에서 컨테이너 실행하여 동작 확인 (선택)
docker run -p 30000:30000 docker.io/my-org/my-service-backend:v1.0.0

# /health 엔드포인트 동작 확인
curl http://localhost:30000/health
# 예상 응답: {"status": "healthy", "timestamp": "..."}

curl http://localhost:30000/info
# 예상 응답: {"name": "my-service", "version": "1.0.0", ...}
```

> 💡 **권장:** 레지스트리에 Push하기 전에 반드시 로컬에서 `/health`, `/info`, `/run` 엔드포인트가 정상 응답하는지 확인하세요.
> 

---

# 6. 레지스트리에 이미지 Push

## 6.1 레지스트리 로그인

```bash
# 플랫폼 담당자로부터 안내받은 레지스트리 주소와 인증 정보 사용
docker login {레지스트리 주소}
# Username / Password 입력
# Docker Hub(docker.io)의 경우 주소 생략해도 가능
```

## 6.2 이미지 Push

```bash
# 백엔드 이미지 Push
docker push docker.io/my-org/my-service-backend:v1.0.0

# 프론트엔드 이미지 Push
docker push docker.io/my-org/my-service-frontend:v1.0.0
```

## 6.3 이미지 태그 규칙 (권장)

| 태그 형식 | 예시 | 사용 시점 |
| --- | --- | --- |
| `v{major}.{minor}.{patch}` | `v1.0.0` | 릴리즈 버전 |
| `{브랜치명}-{커밋해시}` | `main-a1b2c3d` | 개발 중 테스트 |
| `latest` | `latest` | 가장 최신 버전 (단독 사용 비권장) |

> ⚠️ **`latest` 태그 단독 사용 비권장:** 버전 추적이 어렵고, 예상치 못한 버전이 배포될 수 있습니다. 명시적인 버전 태그와 함께 사용하세요.
> 

---

# 7. Helm Chart에 이미지 경로 등록

Push가 완료된 이미지 경로를 Helm Chart의 `values.yaml`에 등록합니다.

```yaml
# values.yaml
backend:
  image: "docker.io/my-org/my-service-backend:v1.0.0"  # ← Push한 이미지 경로
  imagePullPolicy: "IfNotPresent"  # 로컬에 이미지가 없을 때만 pull
  port: 30000                       # Dockerfile의 EXPOSE와 일치해야 함

frontend1:
  image: "docker.io/my-org/my-service-frontend:v1.0.0"
  imagePullPolicy: "IfNotPresent"
  port: 80
```

이후 Helm Chart 설치 방법은 **Tango MSA 탑재 가이드 — 3장 Helm Chart 설치**를 참고하세요.

---

# 8. 자주 발생하는 문제

| 증상 | 원인 | 해결 방법 |
| --- | --- | --- |
| Pod가 `CrashLoopBackOff` 상태 | 컨테이너 실행 중 오류 발생 | `docker run`으로 로컬 실행 후 로그 확인 |
| `/health` 호출 시 연결 거부 | 포트 불일치 또는 엔드포인트 미구현 | Dockerfile `EXPOSE`와 `values.yaml` `targetPort` 일치 여부 확인 |
| 이미지 Pull 실패 (`ImagePullBackOff`) | 레지스트리 인증 실패 또는 이미지 경로 오류 | `docker push` 성공 여부 및 이미지 경로 오타 확인 |
| `/run` 호출 시 500 에러 | 서비스 내부 로직 오류 | Pod 로그 확인 (`kubectl logs <pod명> -n <namespace>`) |
| Nginx가 API 요청을 백엔드로 못 보냄 | `nginx.conf` 프록시 설정 오류 | 백엔드 서비스명 및 포트 확인 |

---

# 부록. 빌드 전 체크리스트

| 항목 | 확인 |
| --- | --- |
| 백엔드에 `/health`, `/info`, `/run` 엔드포인트 구현 완료 | ☐ |
| Dockerfile의 `EXPOSE` 포트가 `values.yaml` `targetPort`와 일치 | ☐ |
| 로컬에서 `docker run`으로 컨테이너 정상 동작 확인 | ☐ |
| `/health` 엔드포인트가 `{"status": "healthy"}` 반환 확인 | ☐ |
| 플랫폼 담당자로부터 레지스트리 주소 및 인증 정보 수령 | ☐ |
| `docker login` 성공 확인 | ☐ |
| `docker push` 성공 확인 | ☐ |
| `values.yaml`에 이미지 경로 등록 완료 | ☐ |