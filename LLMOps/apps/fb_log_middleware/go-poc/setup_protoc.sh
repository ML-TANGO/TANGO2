#!/bin/bash -i

# # Set the protoc version to 28.3
# PROTOC_VERSION=${1:-28.3}
# PROTOC_ZIP=protoc-${PROTOC_VERSION}-linux-x86_64.zip

# # Step 1: Download the specified version of protoc to a temporary location using wget
# wget -O /tmp/${PROTOC_ZIP} https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOC_VERSION}/${PROTOC_ZIP}

# # Step 2: Unzip the protoc binary and headers directly into /usr/local
# sudo unzip -o /tmp/${PROTOC_ZIP} -d /usr/local bin/protoc
# sudo unzip -o /tmp/${PROTOC_ZIP} -d /usr/local 'include/*'

# go package install
go install \
    google.golang.org/protobuf/cmd/protoc-gen-go \
    google.golang.org/grpc/cmd/protoc-gen-go-grpc \
    github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-grpc-gateway # \
    # github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-openapiv2@latest


if ! grep -q "~/go/bin" ~/.bashrc; then
    echo 'export PATH=$PATH:~/go/bin' >> ~/.bashrc
fi

source ~/.bashrc