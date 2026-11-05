msg() {
    message="$1"
    border="========================================"
    echo ""
    echo "$border"
    echo "$message"
    echo "$border"
    echo ""
}

# Nvidia GPU Operator
msg "Create nvidia gpu operator"
sleep 2
./install-nvidia-gpu-operator.sh

# Nvidia Network Operator (including rdmaSharedDevicePlugin, multus, etc.)
msg "Create nvidia network operator"
sleep 2
./install-nvidia-network-operator.sh
