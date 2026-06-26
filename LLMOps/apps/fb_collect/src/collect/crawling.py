import httpx
from parsel import Selector
from urllib.parse import urljoin, urlparse
import csv
import json
import sys
import subprocess
import os
import pytz
from pathlib import Path
from datetime import datetime
import time

sys.path.append("/")
import utils.msa_db.db_collect as collect_db
import utils.msa_db.db_collect_history as history_db

COLLECT_ID=os.getenv("COLLECT_ID",None)
COLLECT_CYCLE=int(os.getenv("COLLECT_CYCLE",60)) # (cycle * cycle unit) convert to second
# COLLECT_INFO = os.getenv("COLLECT_IFNO",None)
DATA_PATH = os.getenv("DATA_PATH", None)
LIMIT_SIZE = int(os.getenv("LIMIT_SIZE", 0))
NAMESPACE = os.getenv("NAMESPACE",None)
HELM_NAME = os.getenv("HELM_NAME",None)

data_path = Path("/jf-data")

def disk_usage(path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    print(result)
    return result.split('\t')[0]

def is_crawlable(url):
    """
    Check if the given URL is allowed to be crawled according to its robots.txt.
    """
    parsed_url = urlparse(url)
    robots_url = urljoin(f"{parsed_url.scheme}://{parsed_url.netloc}", "/robots.txt")

    try:
        response = httpx.get(robots_url, timeout=10)
        if response.status_code == 200:
            robots_txt = response.text
            user_agent_lines = []
            for line in robots_txt.splitlines():
                if line.strip().startswith("User-agent:"):
                    user_agent_lines.append(line)
                elif line.strip().startswith("Disallow:") and user_agent_lines:
                    if "*" in user_agent_lines[-1]:
                        disallowed_path = line.split(":", 1)[1].strip()
                        if urlparse(url).path.startswith(disallowed_path):
                            print(f"URL is disallowed by robots.txt: {disallowed_path}")
                            return False
            return True
        else:
            print("robots.txt not found or inaccessible. Assuming crawlable.")
            return True
    except Exception as e:
        print(f"Error checking robots.txt: {e}")
        return False


def crawl_url(url, output_file_path):
    """
    Crawl the given URL and save all content (text and HTML) to a text file.
    """
    if not is_crawlable(url):
        print("Crawling not allowed for this URL.")
        return

    try:
        global data_path
        response = httpx.get(url, timeout=30)
        if response.status_code == 200:
            all_content = response.text

            with open(data_path.joinpath(output_file_path), "w", encoding="utf-8") as f:
                # f.write(f"URL: {url}\n\n")
                f.write(all_content)

            return response.status_code, output_file_path
        else:
            return response.status_code, f"Failed to fetch URL. HTTP Status: {response.text}"
    except Exception as e:
        return False, f"Error crawling URL: {e}"



if __name__ == "__main__":
    # target_url = "https://example.com"
    if COLLECT_ID:
        collect_info=collect_db.get_collect_info(collect_id=COLLECT_ID)
        while(True):
            relative_path = Path(DATA_PATH)
            server_time = datetime.now()
            local_timezone = pytz.timezone("Asia/Seoul")
            current_time = server_time.astimezone(local_timezone)
            current_time = current_time.strftime("%Y-%m-%d_%H:%M:%S")
            # Crawl the page and get data
            for collect in json.loads(collect_info['collect_information_list']):
                message = ""
                status_code=0
                file_name=f"{collect['name']}_{current_time}.txt"
                status_code, res = crawl_url(url = collect['url'], output_file_path=relative_path.joinpath(file_name))

                history_db.insert_history(collect_id=COLLECT_ID,
                                        collect_info=json.dumps(collect),
                                        status=status_code,
                                        path=str(res))
                result={
                        "collect_id" : COLLECT_ID,
                        "collect_info" : collect,
                        "status" : status_code,
                        "status_message" : message,
                        "relative_path" : str(relative_path.joinpath(file_name))
                    }
                print(f"[collect/crawling] {json.dumps(result)}", file=sys.stdout)

            if LIMIT_SIZE:
                if disk_usage(data_path) >= LIMIT_SIZE:
                    command=f"helm uninstall {HELM_NAME} -n {NAMESPACE}"
                    result = subprocess.run(
                        command,
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    ) 
                    print(result.stdout)
                    history_db.insert_history(collect_id=COLLECT_ID,
                                          collect_info=json.dumps({}),
                                          status=0,
                                          status_message="Storage Usage Exceeded",
                                          path=None)
                    

            time.sleep(COLLECT_CYCLE)
            
