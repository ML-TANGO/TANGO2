from huggingface_hub import login, snapshot_download
import os

token = os.environ.get("JF_HUGGINGFACE_TOKEN")
model_id = os.environ.get("JF_HUGGINGFACE_MODEL_ID")
model_path = os.environ.get("JF_MODEL_PATH")

login(token=token, add_to_git_credential=True)

snapshot_download(repo_id=model_id, local_dir=model_path, local_dir_use_symlinks=False)