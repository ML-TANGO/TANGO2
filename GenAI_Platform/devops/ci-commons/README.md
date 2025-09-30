# /devops/ci-commons

## 개요

여러 devops에서 사용할 법한 template들을 저장해 두는 공간입니다.

특정 언어에서 캐싱하는 과정, 혹은 이미지 빌드와 같이 공통으로 사용할 가능성이 높은 경우
해당 경로에 `<이름>.gitlab-ci.yml` 파일을 만들어 `.`으로 시작하는 job을 만든 뒤
`include: `로 해당 템플릿 파일을 로드하고 `extends` 를 이용하여 진행할 수 있도록 하세요.

템플릿 내의 job들은, `<이름>.gitlab-ci.yml`에서 `<이름>`를 헤더로 하여 `.<이름>-abc` 형태로 작성할 수 있도록 해 주세요.

템플릿 내에서 variable를 사용하는 경우, 명백하게 다른 템플릿과 겹치지 않는 이름으로 해 주세요.
ex) [`python.gitlab-ci.yml`](python.gitlab-ci.yml)에서는 `PIP_CACHE_...` 변수명을 사용

해당 예시로는 [/devops/walking_skeleton_python](/devops/walking_skeleton_python) 경로 내에 있는 [ci.yml 파일](/devops/walking_skeleton_python/ci.yml)을 참고하시기 바랍니다.

혹은 추가적으로 GitLab에서 기본 제공하는 템플릿은 [gitlab 폴더 내부](gitlab)을 참고하세요.