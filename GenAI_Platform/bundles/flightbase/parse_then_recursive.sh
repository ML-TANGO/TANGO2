dependencies="$HELM_CHART_DIR/Chart.yaml"
dep_dir=$(dirname "$dependencies")
CURRENT_DIR=$(pwd)

skip_words="fb_common_lib|fb_common_app" # "keyword_a|keyword_b|hello"

grep -o "file://[^ ]*" "$dependencies" | while read -r line; do
    cd $CURRENT_DIR
    relative_path=$(echo $line | sed -e 's#^file://##' -e 's/"$//')
    if echo "$relative_path" | grep -Eq "$skip_words"; then
        echo "Skipping: $relative_path"
        continue
    fi
    absolute_path=$(cd "$dep_dir" && realpath "$relative_path")
    echo "Dependency build for $absolute_path... (with ../helm_dependency.sh)"
    cd "$absolute_path" 
    cd .. 
    ./helm_dependency.sh
done