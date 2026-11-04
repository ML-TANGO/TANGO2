# Deployment API deco 사용 가이드
- [Deployment API deco 사용 가이드](#deployment-api-deco-사용-가이드)
  - [1. Quick Start](#1-quick-start)
    - [1-1. 사용 목적](#1-1-사용-목적)
    - [1-2. 간단한 사용 예시](#1-2-간단한-사용-예시)
  - [2. deployment_api_deco 패키지 사용하기](#2-deployment_api_deco-패키지-사용하기)
    - [2-1. Overview](#2-1-overview)
    - [2-2. import 방법](#2-2-import-방법)
    - [2-3. deployment_api_deco.api_monitor 데코레이터 사용](#2-3-deployment_api_decoapi_monitor-데코레이터-사용)
      - [2-3-1. parameters](#2-3-1-parameters)
    - [2-4. 에러 기록하기(선택)](#2-4-에러-기록하기선택)
      - [option 1) api return 값에 key value 형태로 포함시키기](#option-1-api-return-값에-key-value-형태로-포함시키기)
      - [option 2) api 내부에서 `set_status` 함수를 통해 error 선언하기](#option-2-api-내부에서-set_status-함수를-통해-error-선언하기)
  - [3. 코드 예시](#3-코드-예시)
    - [3-1. flask api 예시](#3-1-flask-api-예시)
      - [3-1-1. 기본 (에러 정의 미포함)](#3-1-1-기본-에러-정의-미포함)
      - [3-1-2. 에러 정의 포함](#3-1-2-에러-정의-포함)
    - [3-2. 기록 예시](#3-2-기록-예시)


## 1. Quick Start
### 1-1. 사용 목적
api의 응답 시간, 요청 당시 사용 리소스(GPU, CPU, RAM 등), 에러 등을 기록하기 위한 python library
### 1-2. 간단한 사용 예시
```python
import sys
sys.path.append('/addlib')
from deployment_api_deco import api_monitor

@api_monitor(method="POST", router="/", return_status=None)
def api():
    return ""
```

## 2. deployment_api_deco 패키지 사용하기
### 2-1. Overview
- `api_monitor` 데코레이터
  - api 의 method, router 를 parameter 로 받음
    - Flask, Django, CherryPy 의 경우 parameter 생략 가능
  - api의 응답 시간, 사용 리소스(GPU, CPU, RAM 등) 기록
- error 관련 값들 기록
  - 하위 변수들을 선언한 후 기록 할 수 있다.
    - `deployment_api_deco.ERROR_CONDITION` 
    - `deployment_api_deco.ERROR_CONDITION_LOGIC` (선택)
    - `deployment_api_deco.ERROR_CODE_KEY` (선택)
    - `deployment_api_deco.MESSAGE_KEY` (선택)
    - `deployment_api_deco.RETURN_ERROR_OPTIONS` (선택)
- 권장 python web framework
  - Flask v1.0 이상
  - Django v1.6x 이상
  - CherryPy

### 2-2. import 방법
- system path 에 `/addlib` 추가 필요  
- `deployment_api_deco` package 하위에 위치
  ```python
  import sys
  sys.path.append('/addlib')
  from deployment_api_deco import api_monitor
  ```

### 2-3. deployment_api_deco.api_monitor 데코레이터 사용
#### 2-3-1. parameters
- api 의 method, router, use_set_status 를 argument 로 받음 (**Flask, Django, CherryPy 의 경우 생략 가능**)
- `method`(str): POST, GET, PUT, DELETE, OPTIONS 등의 http method
- `router`(str): URL rule. 
  - ex) "/", "/test"
- `use_set_status`(bool): api 내부에서 set_status 함수를 통해 error 선언할지 여부

### 2-4. 에러 기록하기(선택)
아래 두 방식을 통해 에러를 기록할 수 있다.
#### option 1) api return 값에 key value 형태로 포함시키기

- 에러 상태 정의: `deployment_api_deco.ERROR_CONDITION`
  - `{"error_status1":"error1", "error_status2":"error2"}` 와 같이 key value 형태로 error 정의함
  - 사용 예시
    ```python
    import deployment_api_deco
    deployment_api_deco.ERROR_CONDITION={"error_status1":"error1", "error_status2":"error2"}
    ```

- 에러 로직 정의:  `deployment_api_deco.ERROR_CONDITION_LOGIC`
  - ERROR_CONDITION 의 key-value값이 복수 개 일 때의 error count logic (default="or")
  - **"or"** 일 경우 [ERROR_CONDITION](#에러-상태-정의) 에 정의한 에러 key value 중 하나만 일치해도 에러로 count  
  - **"and"** 일 경우 [ERROR_CONDITION](#에러-상태-정의) 에 정의한 에러 key value 전부 일치하면 에러로 count
  - 사용 예시
    ```python
    deployment_api_deco.ERROR_CONDITION_LOGIC="or"
    ```

- 에러 코드 정의: `deployment_api_deco.ERROR_CODE_KEY`
  - 에러 코드는 배포 대시보드의 '비정상처리 기록' 의 상태코드에 기록된다.
    ```python
    deployment_api_deco.ERROR_CODE_KEY="error_code_key"
    ```

- message key 정의: `deployment_api_deco.MESSAGE_KEY`
  - 메세지는 배포 대시보드의 '비정상처리 기록' 의 메세지에 기록된다.
    ```python
    deployment_api_deco.MESSAGE_KEY="message_key"
    ```
  
- return error option 정의: `deployment_api_deco.RETURN_ERROR_OPTIONS`
  - 에러 관련 key 값들을 return 할지 여부 정의하기 (default=True)
    ```python
    deployment_api_deco.RETURN_ERROR_OPTIONS=True
    ```

#### option 2) api 내부에서 `set_status` 함수를 통해 error 선언하기
- status_key, error_code, message를 argument 로 받음
- `status_dic`(str): api_monitor 가 api function 에 자동으로 내려주는 값으로 `args` 로 넣어줘야 함(필수)
- `error_code`(int): 에러의 상태코드로 사용자가 원하는 값으로 지정. 
- `message`(str): api 상태에 대해 기록하고자 하는 message.

## 3. 코드 예시
### 3-1. flask api 예시
#### 3-1-1. 기본 (에러 정의 미포함)
- `@app.route()` 사용 시
  ```python
  from flask import Flask
  app = Flask(__name__)

  @app.route("/", methods=['POST'])
  @api_monitor()
  def api():
      return ""
  ```

- `flask.views.MethodView` 사용 시
  ```python
  from flask.views import MethodView

  class run_api(MethodView):
      @api_monitor()
      def post():
          return ""
  ```

#### 3-1-2. 에러 정의 포함
- api return 값에 key value 형태로 포함시키는 경우
  ```python
  import sys
  sys.path.append('/addlib')
  from deployment_api_deco import api_monitor
  # error 정의 영역
  import deployment_api_deco
  deployment_api_deco.ERROR_CONDITION={"error_status1":"error1", "error_status2":"error2"}
  deployment_api_deco.ERROR_CONDITION_LOGIC="or"
  deployment_api_deco.ERROR_CODE_KEY="error_code_key"
  deployment_api_deco.MESSAGE_KEY="message_key"
  deployment_api_deco.RETURN_ERROR_OPTIONS=False

  from flask import Flask
  app = Flask(__name__)

  @app.route("/", methods=['POST'])
  @api_monitor()
  def api():

      """function"""
      output["text"]=prediction_function(input)
      output["error_status1"]="success"
      output["error_code_key"]=2000
      if [ERROR CASE 1]:
          output["error_status1"]="error1"
          output["error_code_key"]=3000
          output["message_key"]="error 1"

      elif [ERROR CASE 2]:
          output["error_status1"]="error1"
          output["error_status2"]="error2"
          output["error_code_key"]=4000
          output["message_key"]="error 2"

      return output

  if __name__ == "__main__":
      app.run('0.0.0.0',8555,threaded=True)
      
  ```
- api 내부에서 `set_status` 함수를 통해 error 선언하는 경우
  ```python
  ...
  import sys
  sys.path.append('/addlib')
  from deployment_api_deco import api_monitor, set_status
  # error 정의 영역 필요 없음

  from flask import Flask
  app = Flask(__name__)

  @app.route("/", methods=['POST'])
  @api_monitor(use_set_status=True)
  def api(**args): # 함수 argument 에 **args 추가 필요

      """function"""
      output["text"]=prediction_function(input)
      set_status(status_dic=args, message="success")
      if [ERROR CASE 1]:
          set_status(status_dic=args, error_code=3000, message="error 1")

      elif [ERROR CASE 2]:
          set_status(status_dic=args, error_code=4000, message="error 2")

      return output
  ...   
  ```

api return 값에 포함시키는 경우 `RETURN_ERROR_OPTIONS=False`이기 때문에 api 의 return 값의 key 에는 `"text"` 만 담김  
`ERROR_CONDITION_LOGIC="or"` 기 때문에 `[ERROR CASE 1]`, `[ERROR CASE 2]` 둘 다 error 로 기록됨  
(`ERROR_CONDITION_LOGIC="and"` 일 경우 `[ERROR CASE 2]` 만 error 로 기록됨)  
  
### 3-2. 기록 예시

|일시 | 워커 | 상태코드 | 메세지 | 엔드포인트 |
|---|---|---|---|---|
|2022-01-27 13:13:19 | 워커 262 | 3000 | error 1 | POST / |
|2022-01-27 13:13:20 | 워커 262 | 4000 | error 2 | POST / |
