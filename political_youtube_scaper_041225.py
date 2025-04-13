import os
import sys
import time
import json
import random
import datetime
import base64
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from github import Github, GithubException

# Chrome 옵션 설정 (헤드리스 모드)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# Chrome 바이너리 경로 지정 (Render 환경에 설치된 Chromium의 경로로 수정)
chrome_options.binary_location = "/usr/bin/chromium-browser"

# 처리할 YouTube 채널 목록
channels = [
    {"channel": "성창경TV", "channel_url": "https://www.youtube.com/@scktv100/videos"},
    {"channel": "이봉규TV", "channel_url": "https://www.youtube.com/@leebongkyu_tv/videos"},
    {"channel": "신의한수", "channel_url": "https://www.youtube.com/@tubeshin/videos"},
    {"channel": "고성국TV", "channel_url": "https://www.youtube.com/@kosungkooktv/videos"},
    {"channel": "배승희_변호사", "channel_url": "https://www.youtube.com/@tatabuta/videos"},
    {"channel": "펜앤마이크TV", "channel_url": "https://www.youtube.com/@penn1TV/videos"},
    {"channel": "서정욱TV", "channel_url": "https://www.youtube.com/@%EC%84%9C%EC%A0%95%EC%9A%B1TV/videos"},
    {"channel": "신인균의_국방TV", "channel_url": "https://www.youtube.com/@KDNKukbangTV/videos"},
    {"channel": "[정광용TV]레지스탕스TV", "channel_url": "https://www.youtube.com/@TVTV-rc1hd/videos"},
    {"channel": "최병묵의_FACT", "channel_url": "https://www.youtube.com/@choifact/videos"},
    {"channel": "김어준의_겸손은힘들다_뉴스공장", "channel_url": "https://www.youtube.com/@gyeomsonisnothing/streams"},
    {"channel": "[팟빵]매불쇼", "channel_url": "https://www.youtube.com/@maebulshow/streams"},
    {"channel": "스픽스", "channel_url": "https://www.youtube.com/@SPEAKS_TV/videos"},
    {"channel": "[공식]새날", "channel_url": "https://www.youtube.com/@saenal/videos"},
    {"channel": "장윤선의_취재편의점", "channel_url": "https://www.youtube.com/@%EC%B7%A8%EC%9E%AC%ED%8E%B8%EC%9D%98%EC%A0%90/videos"},
    {"channel": "백운기의_정어리TV", "channel_url": "https://www.youtube.com/@%EB%B0%B1%EC%9A%B4%EA%B8%B0%EC%9D%98%EC%A0%95%EC%96%B4%EB%A6%ACTV/videos"},
    {"channel": "언론_알아야_바꾼다", "channel_url": "https://www.youtube.com/@unalba/videos"},
    {"channel": "사장남천동", "channel_url": "https://www.youtube.com/@%EC%82%AC%EC%9E%A5%EB%82%A8%EC%B2%9C%EB%8F%99/streams"},
    {"channel": "김용민TV", "channel_url": "https://www.youtube.com/@kimyongminTV/streams"},
    {"channel": "정치파랑새", "channel_url": "https://www.youtube.com/@%EC%A0%95%EC%B9%98%EC%9D%BC%ED%95%99/videos"}
]

# 상수 정의
MAX_VIDEOS_PER_CHANNEL = 5  # 채널당 최대 수집 비디오 수
# 로컬 저장 파일 (스크래핑 후 GitHub 업데이트 대상)
OUTPUT_FILE = "youtube_videos.jsonl"


def safe_read_jsonl_file(repo, file_path):
    """
    GitHub 저장소에서 JSONL 파일을 읽어 기존 데이터를 반환.
    파일이 존재하지 않으면 빈 리스트와 None(sha)을 반환.
    """
    try:
        contents = repo.get_contents(file_path)
        if contents.encoding == "base64" and contents.content:
            try:
                content_string = base64.b64decode(contents.content).decode("utf-8")
                existing_data = []
                for line in content_string.splitlines():
                    if line.strip():
                        try:
                            item = json.loads(line)
                            existing_data.append(item)
                        except json.JSONDecodeError:
                            pass
                return existing_data, contents.sha
            except Exception:
                return [], contents.sha
        else:
            return [], contents.sha
    except GithubException as e:
        if e.status == 404:
            return [], None
        else:
            return [], None
    except Exception:
        return [], None


def convert_to_jsonl(data_list):
    """리스트 형태의 데이터를 JSONL 포맷 문자열로 변환"""
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in data_list)


def update_github_jsonl(new_data):
    """
    GitHub 저장소의 JSONL 파일을 불러와 기존 데이터와 새 데이터를 결합한 후,
    video_url이 중복되는 경우 scraping_time 기준 최신 데이터만 남기고 업데이트.
    """
    if not new_data:
        return True

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        return False

    # 아래 repo_name과 file_path는 사용 환경에 맞게 수정하세요.
    repo_name = "jonghhhh/political_youtube_scaper"  # 예: "jonghhhh/youtube_data"
    file_path = "youtube_videos.jsonl"

    try:
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        existing_data, sha = safe_read_jsonl_file(repo, file_path)
        combined_data = existing_data + new_data

        # video_url 기준 deduplication (최신 scraping_time 데이터만 남김)
        deduped_records = {}
        for record in combined_data:
            url = record.get("video_url", "")
            if url:
                if (url not in deduped_records) or (
                    record.get("scraping_time", "") < deduped_records[url].get("scraping_time", "")
                ):
                    deduped_records[url] = record

        jsonl_content = convert_to_jsonl(list(deduped_records.values()))
        commit_message = f"Update videos data at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if sha:
            repo.update_file(file_path, commit_message, jsonl_content, sha)
        else:
            repo.create_file(file_path, commit_message, jsonl_content)
        return True
    except Exception:
        return False


def main():
    # 스크래핑 시작 시각 (년월일시분 형식)
    scraping_time = datetime.datetime.now().strftime("%Y%m%d%H%M")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    new_videos_data = []

    try:
        for channel_info in channels:
            channel_name = channel_info["channel"]
            channel_url = channel_info["channel_url"]
            driver.get(channel_url)
            time.sleep(2)  # 페이지 로딩 대기
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-grid-video-renderer, ytd-rich-item-renderer")[:MAX_VIDEOS_PER_CHANNEL]
            for video in videos:
                try:
                    title_element = video.find_element(By.CSS_SELECTOR, "#video-title, #title-wrapper")
                    title = title_element.text or title_element.get_attribute("title")
                    link_element = video.find_element(By.CSS_SELECTOR, "a#thumbnail")
                    video_url = link_element.get_attribute("href")
                    new_videos_data.append({
                        "channel": channel_name,
                        "channel_url": channel_url,
                        "video_title": title,
                        "video_url": video_url,
                        "scraping_time": scraping_time
                    })
                except Exception:
                    continue
            time.sleep(random.uniform(1, 2))
    except Exception:
        pass
    finally:
        driver.quit()

    update_github_jsonl(new_videos_data)


if __name__ == "__main__":
    main()
