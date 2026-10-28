#!/bin/bash
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

# ============================================================
# CLI INFO
# ============================================================
CLI='nerdctl'
read -p "Image Build CLI? $CLI? (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    # CLI: docker
    CLI='docker'
    read -p "Image Build CLI? $CLI (y/n) " RESPONSE
    if [ "$RESPONSE" == "n" ]; then
        exit 0
    fi 
    INSECURE_REGISTRY=''
else
    # CLI: nerdctl
    ### protocol
    PROTOCOL='http'
    read -p "Image registry protocol? $PROTOCOL (y/n) " RESPONSE
    if [ "$RESPONSE" == "n" ]; then
        PROTOCOL='https'
        echo "using protocol $PROTOCOL"
    fi

    ### insecure
    if [ "$PROTOCOL" == "http" ]; then
        INSECURE_REGISTRY='--insecure-registry'
    else
        INSECURE_REGISTRY=''
    fi
fi

# ============================================================
# IMAGE INFO
# ============================================================
REGISTRY="registry.jonathan.acryl.ai"
read -p "Image registry url? $REGISTRY (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    read -p "Enter Image registry url: " REGISTRY
fi

VERSION="0.3.0"
read -p "Image registry version? $VERSION (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    read -p "Enter Image version: " VERSION
fi

read -p "build ALL? (y/n) " BUILD_ALL
read -p "Image save tar? (y/n) " SAVE

echo REGISTRY: $REGISTRY
echo VERSION: $VERSION
echo BUILD_ALL: $BUILD_ALL
echo SAVE: $SAVE


# ============================================================
# IMAGE BUILD
# ============================================================

IMAGE=$REGISTRY/jfb-system/REPLACE_app:$VERSION
BUILD_COMMAND="$CLI build --no-cache --tag $IMAGE -f Dockerfile .."
PUSH_COMMAND="$CLI push $INSECURE_REGISTRY $IMAGE"
SAVE_COMMAND="$CLI save -o REPLACE.tar $IMAGE"

if [ "$BUILD_ALL" == "y" ]; then

    # devops/run.sh(fb_*) + run_llm.sh(evaluation·data_pipeline) 가 배포하는 앱 = Dockerfile 이 있는 디렉터리.
    # 없는 디렉터리를 넣으면 cd 가 실패해 직전 앱을 엉뚱한 태그로 다시 빌드하므로 아래 cd 에서 중단한다.
    dir=("dashboard" "dataset" "deployment" "external_container" "image" "monitoring" "notification" "resource" "scheduler" "user" "workspace" "option" "alert_management" "ingress_management" "collect" "preprocessing" "pipeline" "analyzing" "synthesis" "evaluation" "data_pipeline")
    # dir=("model" "playground")   # llm_model·llm_playground 는 일괄 대상 밖 — "APP NAME?" 에 model/playground 로 개별 빌드
    # 주: "evaluation" → llm_evaluation (아래 llm_$APP 분기). 외부컨테이너(evaluate/convert/
    #     evaluate_benchmark_mock)는 apps/evaluate 등과 동일하게 ad-hoc 빌드(이 배열 밖).
    for APP in "${dir[@]}"; do
        if [[ "$APP" == "playground" || "$APP" == "model" || "$APP" == "rag"  || "$APP" == "prompt" || "$APP" == "evaluation" || "$APP" == "data_pipeline" ]]; then
            echo cd $BASE_DIR/llm_$APP
            cd $BASE_DIR/llm_$APP || { echo "ERROR: $BASE_DIR/llm_$APP 없음 — 중단" >&2; exit 1; }
        else
            echo cd $BASE_DIR/fb_$APP
            cd $BASE_DIR/fb_$APP || { echo "ERROR: $BASE_DIR/fb_$APP 없음 — 중단" >&2; exit 1; }
        fi

        command="${BUILD_COMMAND/REPLACE/"$APP"}"
        echo $command
        $command

        command="${PUSH_COMMAND/REPLACE/"$APP"}"
        echo $command
        $command

        if [ "$SAVE" == "y" ]; then
            command="${SAVE_COMMAND/REPLACE/"$APP"}"
            echo $command
            $command
        fi
    done

elif [ "$BUILD_ALL" == "n" ]; then

    read -p "APP NAME? (ex. dashboard) " APP

    if [[ "$APP" == "playground" || "$APP" == "model" || "$APP" == "rag"  || "$APP" == "prompt" || "$APP" == "evaluation" || "$APP" == "data_pipeline" ]]; then
        echo cd $BASE_DIR/llm_$APP
        cd $BASE_DIR/llm_$APP || { echo "ERROR: $BASE_DIR/llm_$APP 없음 — 중단" >&2; exit 1; }
    else
        echo cd $BASE_DIR/fb_$APP
        cd $BASE_DIR/fb_$APP || { echo "ERROR: $BASE_DIR/fb_$APP 없음 — 중단" >&2; exit 1; }
    fi

    command="${BUILD_COMMAND/REPLACE/"$APP"}"
    echo $command
    $command

    command="${PUSH_COMMAND/REPLACE/"$APP"}"
    echo $command
    $command

    if [ "$SAVE" == "y" ]; then
        command="${SAVE_COMMAND/REPLACE/"$APP"}"
        echo $command
        $command
    fi
fi
