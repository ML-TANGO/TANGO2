from huggingface_hub import snapshot_download

local_dir = snapshot_download(
    repo_id="meta-llama/Llama-3.2-1B",
    local_dir="./Llama-3.2-1B"
)
print("Downloaded to:", local_dir)

