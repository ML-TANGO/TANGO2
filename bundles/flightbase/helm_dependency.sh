# Save the current directory
CURRENT_DIR=$(pwd)

# Copy kube configuration file
mkdir -p "${COMMONAPP_CHART_DIR}/file"
echo "Copy ${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube to ${COMMONAPP_CHART_DIR}/file/"
cp -r "${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube" "${COMMONAPP_CHART_DIR}/file/"

# Run helm dependency build for common app
echo "Building commonapp dependency from $CURRENT_DIR..."
cd "${COMMONAPP_CHART_DIR}"
helm dependency build

# Return to the saved current directory
cd "$CURRENT_DIR"

# call other script that parse Chart.yaml and do all dependency builds
echo "Building all other dependencies..."
./parse_then_recursive.sh

# Return to the saved current directory
cd "$CURRENT_DIR"

# Go to ./helm and run helm dependency build
echo "Building $CURRENT_DIR dependency..."
cd ./helm
helm dependency build

# Go back to original directory after operations
cd "$CURRENT_DIR"