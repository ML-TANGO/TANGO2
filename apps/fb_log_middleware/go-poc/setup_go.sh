#!/bin/bash -i

# Set the Go version as a variable, defaulting to 1.22.4 if not provided
GO_VERSION=${1:-1.22.4}

# Step 1: Download the Go tarball to a temporary location
curl -o /tmp/go${GO_VERSION}.linux-amd64.tar.gz https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz

# Step 2: Remove any existing Go installation in /usr/local/go and extract the new version
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf /tmp/go${GO_VERSION}.linux-amd64.tar.gz

# Step 3: Add /usr/local/go/bin to the PATH if not already added
if ! grep -q "/usr/local/go" ~/.bashrc; then
    echo 'export PATH=$PATH:/usr/local/go' >> ~/.bashrc
fi

if ! grep -q "/usr/local/go/bin" ~/.bashrc; then
    echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
fi

source ~/.bashrc
