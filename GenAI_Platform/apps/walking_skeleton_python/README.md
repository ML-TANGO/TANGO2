# apps/walking_skeleton_python

## 개요

파이썬 마이크로서비스를 위한 워킹 스켈레톤 코드입니다.

해당 폴더를 `/apps` 폴더 내에 복사하고, `/devops` 폴더 내에서도 [/devops/walking_skeleton_python/README.md](/devops/walking_skeleton_python/README.md)를 참고하여 복사해서 진행해 주세요.

## SimpleFastAPI

이 워킹 스켈레톤 코드는 FastAPI를 이용한 백엔드 서비스를 만드는 프로젝트입니다.

파이썬에서 FastAPI를 이용한 백엔드 코드를 작성하였으며, PyLint를 활용한 정적 검사, pytest를 이용한 유닛 테스트를 수행합니다.

백엔드 코드는 [main.py](main.py), 유닛 테스트 코드는 [test_main.py](test_main.py)를 참고하세요.
도커파일의 경우 [Dockerfile](Dockerfile) 파일을, 이외 헬름 및 정적 검사와 유닛 테스트 코드는 [/devops/walking_skeleton_python/README.md](/devops/walking_skeleton_python/README.md)를 확인하시기 바랍니다.


본 프로젝트의 Step-by-Step에 대해서는 노션에 관련 문서가 있으니, 접근 가능한 경우 `SimpleFastAPI` 로 검색하여 확인하시기 바랍니다.

## 실행

해당 프로젝트의 실행을 위해서는 Python이 설치되고, [requirements.txt](requirements.txt)가 pip로 설치되어야 합니다.
해당 프로젝트를 실행하려면 [execute](execute) 파일을 실행하면 됩니다.



