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

def crawl_url(url, output_file):
    """
    Crawl the given URL and save all content (text and HTML) to a text file.
    """
    if not is_crawlable(url):
        print("Crawling not allowed for this URL.")
        return

    try:
        response = httpx.get(url, timeout=10)
        if response.status_code == 200:
            all_content = response.text

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"URL: {url}\n\n")
                f.write(all_content)

            print(f"All page content saved to {output_file}")
        else:
            print(f"Failed to fetch URL. HTTP Status: {response.status_code}")
    except Exception as e:
        print(f"Error crawling URL: {e}")

# Example usage
if __name__ == "__main__":
    server_time = datetime.now()
    local_timezone = pytz.timezone("Asia/Seoul")
    current_time = server_time.astimezone(local_timezone)
    current_time = current_time.strftime("%Y-%m-%d_%H:%M:%S")
    target_url = "http://quotes.toscrape.com"
    file_name=f"output_{current_time}.txt"
    crawl_url(target_url, file_name)

