nohup docker run --rm --gpus '"device=0"'  -e HF_TOKEN=    -v $(pwd)/out:/workspace/out     -v hf_cache:/workspace/.hf_cache     qwen3-mixatis:latest bash run_experiment.sh full > log.out 2>&1 &
