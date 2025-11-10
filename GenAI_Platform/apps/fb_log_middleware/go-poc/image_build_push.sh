#!/bin/bash

# 기본 태그 설정
DEFAULT_TAG="registry.jonathan.acryl.ai/jfb-system/fb_log_middleware:0.1.0"

# 함수: 사용법 출력
usage() {
    echo "사용법: $0 [태그]"
    echo "태그가 지정되지 않으면 기본값 ($DEFAULT_TAG)이 사용됩니다."
    exit 1
}

# 함수: 오류 처리
handle_error() {
    echo "에러: $1"
    exit 1
}

# 메인 로직
main() {
    # 태그 설정
    local tag="${1:-$DEFAULT_TAG}"
    
    echo "사용할 태그: $tag"
    
    # nerdctl build 실행
    echo "이미지 빌드 중..."
    nerdctl build . --tag "$tag" || handle_error "이미지 빌드 실패"
    
    # nerdctl push 실행
    echo "이미지 푸시 중..."
    nerdctl push --insecure-registry "$tag" || handle_error "이미지 푸시 실패"
    
    echo "작업이 성공적으로 완료되었습니다!"
}

# 스크립트 실행
main "$@"