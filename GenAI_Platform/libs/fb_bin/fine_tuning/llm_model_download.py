import argparse
import shutil
import os
import sys
import torch

from huggingface_hub import login, snapshot_download
from requests.exceptions import HTTPError, ConnectionError, Timeout


def mode_directory(save_directory, dir_name="models--"):
    # 다운로드된 디렉토리 구조 변경
    for root, dirs, files in os.walk(save_directory):
        for dir_name in dirs:
            # "models--"로 시작하는 하위 디렉토리를 찾음
            if dir_name.startswith(dir_name):
                downloaded_model_path = os.path.join(root, dir_name)

                # 다운로드된 모든 파일을 save_directory로 이동
                for item in os.listdir(downloaded_model_path):
                    shutil.move(os.path.join(downloaded_model_path, item), save_directory)

                # 빈 디렉토리 제거
                shutil.rmtree(downloaded_model_path)
                break  # 해당 디렉토리만 찾으면 되므로 루프 종료

        # 첫 번째 루프 이후 break로 탈출
        break

def download_model(model_id: str, token: str, dst_model_path: str, latest_checkpoint_path : str):
    """
    Hugging Face에서 주어진 모델 ID로 모델을 다운로드하고 저장하는 함수.

    Parameters:
    model_id (str): 다운로드할 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.
    dst_model_path (str): 모델이 저장될 디렉토리 경로. 기본값은 "./model".
    """
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        # Hugging Face 로그인 (토큰 기반)
        login(token=token, add_to_git_credential=True)

        # 저장할 디렉토리 생성
        os.makedirs(dst_model_path, exist_ok=True)

        # 토크나이저 및 모델 다운로드
        print(f"Downloading model '{model_id}'...")
        # tokenizer = AutoTokenizer.from_pretrained(model_id, use_auth_token=token)
        snapshot_download(repo_id=model_id, local_dir=dst_model_path, local_dir_use_symlinks=False)
        # 모델 및 토크나이저 저장
        # tokenizer.save_pretrained(tokenizer_dir)
        # mode_directory(dst_model_path) # depth 줄이기 
        print(f"Model '{model_id}' has been downloaded and saved to '{dst_model_path}'.")
        # latest checkpoint로 source model 옮기기
        shutil.copytree(dst_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{dst_model_path}' has been copied to '{latest_checkpoint_path}'.") 
    except HTTPError as e:
        # 허깅페이스 API 관련 오류 처리 (모델 ID가 잘못되었을 경우 포함)
        print(f"Error: Hugging Face model '{model_id}' not found or invalid token.")
        print(f"Details: {e}")
        sys.exit(0)
    
    except (ConnectionError, Timeout) as e:
        # 네트워크 연결 문제
        print(f"Error: Network issue occurred while downloading the model '{model_id}'.")
        print(f"Details: {e}")
        sys.exit(0)
    except OSError as e:
        # 파일 시스템 오류 (디렉토리 생성, 저장 문제 등)
        print(f"Error: Problem with saving the model to '{dst_model_path}'.")
        print(f"Details: {e}")
        sys.exit(0)
    except Exception as e:
        # 기타 예상치 못한 예외 상황 처리
        print(f"An unexpected error occurred: {e}")
        sys.exit(0)
    
    
def copy_commit_model(  dst_model_path: str,  latest_checkpoint_path : str, \
    src_model_path: str = "", src_model_log_path : str = "", dst_log_dir : str ="", is_commit: int = 0):
    try:
        if is_commit: # 새로운 모델 생성 시 다른 모델의 commit을 가져올 경우
            shutil.copytree(src_model_path, dst_model_path, dirs_exist_ok=True)
            print(f"Folder '{src_model_path}' has been copied to '{dst_model_path}'.") 
            shutil.copytree(src_model_path, latest_checkpoint_path, dirs_exist_ok=True)
            print(f"Folder '{src_model_path}' has been copied to '{latest_checkpoint_path}'.") 
        else: # 파인튜닝 후 commit 시 
            # 복사 목록
            # 1. latest checkpoint 복사 
            # 2. training log 복사 
            shutil.copytree(latest_checkpoint_path, dst_model_path, dirs_exist_ok=True)
            print(f"Folder '{latest_checkpoint_path}' has been copied to '{dst_model_path}'.") 
            # src_model_log_path = f"/models/{model_name}/logs"
            shutil.copytree(src_model_log_path, dst_log_dir, dirs_exist_ok=True)
            print(f"Folder '{src_model_log_path}' has been copied to '{dst_log_dir}'.")
    except shutil.Error as e:
        print(f"Error occurred while copying folder: {e}")
        sys.exit(0)


def stop(tmp_model_path : str, latest_checkpoint_path : str):
    try:
        shutil.rmtree(latest_checkpoint_path)
        print(f"Folder '{latest_checkpoint_path}'rm success.") 
        shutil.copytree(tmp_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{tmp_model_path}' has been copied to '{latest_checkpoint_path}'.")
    except shutil.Error as e:
        print(f"Error occurred while copying folder: {e}")
        sys.exit(0)

def commit_load(latest_checkpoint_path : str, load_commit_model_path : str):
    try:
        shutil.rmtree(latest_checkpoint_path)
        print(f"Folder '{latest_checkpoint_path}'rm success.")
        shutil.copytree(load_commit_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{load_commit_model_path}' has been copied to '{latest_checkpoint_path}'.")
    except shutil.Error as e:
        print(f"Error occurred while copying folder: {e}")
        sys.exit(0)

if __name__ == "__main__":
    import argparse
    import sys

    # argparse를 사용하여 CLI 인자를 처리
    parser = argparse.ArgumentParser(description="Manage Hugging Face models and directory operations.")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Choose an operation: download_model, copy_commit_model, stop_fine_tuning, load_commit_model.")
    
    # download_model 서브커맨드
    download_parser = subparsers.add_parser("download_model", help="Download a Hugging Face model.")
    download_parser.add_argument("--model_id", type=str, help="The model ID from Hugging Face (e.g., 'bert-base-uncased').")
    download_parser.add_argument("--token", type=str, help="Your Hugging Face API token.")
    download_parser.add_argument("--dst_model_path", type=str, help="The directory where the model will be saved (default: './model').")
    download_parser.add_argument("--latest_checkpoint_path", type=str, help="The directory for the latest model checkpoint.")

    # copy_commit_model 서브커맨드
    commit_parser = subparsers.add_parser("copy_commit_model", help="Copy or commit model and related files.")
    commit_parser.add_argument("--dst_model_path", type=str, help="The target directory for the model.")
    commit_parser.add_argument("--dst_log_dir", type=str, help="The target directory for logs.")
    commit_parser.add_argument("--latest_checkpoint_path", type=str, help="The path to the latest model checkpoint.")
    commit_parser.add_argument("--src_model_path", type=str, default="", help="Source model directory (if copying from an existing model).")
    commit_parser.add_argument("--src_model_log_path", type=str, default="", help="Source log directory (if copying logs from an existing model).")
    commit_parser.add_argument("--is_commit", type=int, default=0, choices=[0, 1], help="Whether this is a commit operation (1 for yes, 0 for no).")
    
    # stop_fine_tuning 서브커맨드
    stop_parser = subparsers.add_parser("stop_fine_tuning", help="Stop fine-tuning.")
    stop_parser.add_argument("--latest_checkpoint_path", type=str, help="The path to the latest model checkpoint.")
    stop_parser.add_argument("--tmp_model_path", type=str, help="The target directory for logs.")
    
    # load_commit_model 서브커맨드
    load_parser = subparsers.add_parser("load_commit_model", help="Load committed model.")
    load_parser.add_argument("--latest_checkpoint_path", type=str, help="The path to the latest model checkpoint.")
    load_parser.add_argument("--load_commit_model_path", type=str, help="The path to the committed model.")

    # 인자 파싱
    args = parser.parse_args()

    if args.command == "download_model":
        # download_model 함수 호출
        download_model(
            model_id=args.model_id,
            token=args.token,
            dst_model_path=args.dst_model_path,
            latest_checkpoint_path=args.latest_checkpoint_path
        )
    elif args.command == "copy_commit_model":
        # copy_commit_model 함수 호출
        copy_commit_model(
            dst_model_path=args.dst_model_path,
            dst_log_dir=args.dst_log_dir,
            latest_checkpoint_path=args.latest_checkpoint_path,
            src_model_path=args.src_model_path,
            src_model_log_path=args.src_model_log_path,
            is_commit=args.is_commit
        )
    elif args.command == "stop_fine_tuning":
        # stop_fine_tuning 함수 호출
        stop(
            latest_checkpoint_path=args.latest_checkpoint_path,
            tmp_model_path=args.tmp_model_path
        )
    elif args.command == "load_commit_model":
        # load_commit_model 함수 호출
        commit_load(
            latest_checkpoint_path=args.latest_checkpoint_path,
            load_commit_model_path=args.load_commit_model_path,
        )
    else:
        print("Invalid command. Use 'download_model', 'copy_commit_model', 'stop_fine_tuning', or 'load_commit_model'.")
        sys.exit(1)