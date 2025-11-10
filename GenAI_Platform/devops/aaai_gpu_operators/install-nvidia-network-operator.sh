# add mellanox Helm charts repo
# helm repo add mellanox https://mellanox.github.io/network-operator --force-update
# helm repo update

# install Nvidia Network Operator
helm install -n network-operator --create-namespace \
	  -f network-operator-values.yaml --wait --version 1.4.0 \
	    network-operator network-operator/
		#mellanox/network-operator
