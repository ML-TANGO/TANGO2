#!/bin/bash

# Directory paths
tmp_model_dir="/tmp_model"
model_dir="/model"

# Find the checkpoint-* folder with the largest step number
latest_checkpoint=$(find "$tmp_model_dir" -maxdepth 1 -type d -name "checkpoint-*" | sort -V | tail -n 1)

# Check if a checkpoint folder was found
if [ -z "$latest_checkpoint" ]; then
    echo "No checkpoint-* folder found. Exiting."
    exit 0
fi

# Move contents of the latest checkpoint folder to /tmp_model
mv "$latest_checkpoint"/* "$tmp_model_dir"

rm -rf /tmp_model/checkpoint-*

# Copy contents of /tmp_model to /model
cp "$tmp_model_dir"/* "$model_dir"

echo "Contents moved and copied successfully."