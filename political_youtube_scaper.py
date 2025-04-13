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
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-setuid-sandbox")
chrome_options.add_argument("--lang=ko-KR")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Render.com에서는 특정 경로에 Chrome이 있을 수 있음
# 여러 가능한 경로를 시도
possible_chrome_paths = [
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable"
]

# 존재하는 Chrome 바이너리 찾기
chrome_binary = None
for path in possible_chrome_paths:
    if os.path.exists(path):
        chrome_binary = path
        break

# 바이너리 경로 설정 (발견된 경우에만)
if chrome_binary:
    chrome_options.binary_location = chrome_binary

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
        # 서울 시간으로 커밋 메시지 생성
        seoul_timezone = datetime.timezone(datetime.timedelta(hours=9))
        seoul_time = datetime.datetime.now(seoul_timezone)
        
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
        commit_message = f"Update videos data at {seoul_time.strftime('%Y-%m-%d %H:%M:%S')} KST"
        if sha:
            repo.update_file(file_path, commit_message, jsonl_content, sha)
        else:
            repo.create_file(file_path, commit_message, jsonl_content)
        return True
    except Exception as e:
        print(f"GitHub 업데이트 실패: {str(e)}")
        return False


def setup_webdriver():
    """
    Render.com 환경에 맞는 웹드라이버 설정을 생성
    """
    try:
        # 방법 1: 기본 설정으로 ChromeDriverManager 사용
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    except Exception as e:
        print(f"기본 방법 실패: {str(e)}")
        try:
            # 방법 2: Service 객체 없이 직접 실행
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"방법 2 실패: {str(e)}")
            try:
                # 방법 3: 환경 변수로 직접 경로 지정
                chrome_driver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
                return webdriver.Chrome(service=Service(chrome_driver_path), options=chrome_options)
            except Exception as e:
                print(f"모든 Webdriver 설정 방법 실패: {str(e)}")
                sys.exit(1)


def main():
    # 스크래핑 시작 시각 (서울 시간 기준, 년월일시분 형식)
    seoul_timezone = datetime.timezone(datetime.timedelta(hours=9))  # UTC+9 (한국 시간)
    scraping_time = datetime.datetime.now(seoul_timezone).strftime("%Y%m%d%H%M")
    print(f"스크래핑 시작 시각 (서울): {datetime.datetime.now(seoul_timezone).strftime('%Y-%m-%d %H:%M:%S')}")
    new_videos_data = []
    
    print(f"Chrome 바이너리 경로: {chrome_binary or '찾지 못함'}")
    
    try:
        # 웹드라이버 설정
        driver = setup_webdriver()
        
        # 모든 채널 처리
        for channel_info in channels:
            channel_name = channel_info["channel"]
            channel_url = channel_info["channel_url"]
            
            try:
                print(f"\n==== {channel_name} 처리 시작 ====")
                # 채널별로 새 드라이버 세션 사용
                driver.quit()
                driver = setup_webdriver()
                
                # 페이지 로드
                print(f"{channel_url} 로딩 중...")
                driver.get(channel_url)
                time.sleep(5)  # 로딩 대기 시간 증가
                
                # 페이지 로드 확인
                page_title = driver.title
                print(f"페이지 제목: {page_title}")
                
                # JavaScript 실행으로 페이지 완전 로드 확인
                is_loaded = driver.execute_script("return document.readyState") == "complete"
                print(f"페이지 로드 상태: {'완료' if is_loaded else '미완료'}")
                
                # YouTube 페이지 렌더링 대기 (더 많은 스크롤)
                for i in range(5):
                    driver.execute_script(f"window.scrollBy(0, {500 * (i+1)})")
                    time.sleep(1)
                
                # 여러 가능한 CSS 선택자 시도
                selectors = [
                    "ytd-grid-video-renderer, ytd-rich-item-renderer",
                    "ytd-grid-video-renderer", 
                    "ytd-rich-item-renderer",
                    "#contents ytd-rich-item-renderer",
                    "#contents > ytd-rich-item-renderer",
                    "ytd-rich-grid-media"
                ]
                
                videos = []
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            videos = elements[:MAX_VIDEOS_PER_CHANNEL]
                            print(f"{selector} 선택자로 {len(videos)}개 비디오 발견")
                            break
                    except Exception as e:
                        print(f"{selector} 선택자 시도 실패: {str(e)}")
                
                if not videos:
                    print(f"주의: {channel_name}에서 비디오를 찾지 못했습니다!")
                    # 전체 페이지 HTML 일부 출력 (디버깅용)
                    page_source = driver.page_source[:500]
                    print(f"페이지 소스 일부: {page_source}")
                    continue
                
                for i, video in enumerate(videos):
                    try:
                        print(f"\n비디오 {i+1} 처리 중...")
                        
                        # 제목 찾기 (여러 선택자 시도)
                        title = None
                        title_selectors = ["#video-title", "#title-wrapper", "h3", "a[title]"]
                        for title_selector in title_selectors:
                            try:
                                title_element = video.find_element(By.CSS_SELECTOR, title_selector)
                                title = title_element.text or title_element.get_attribute("title")
                                if title:
                                    print(f"제목 찾음: {title[:50]}...")
                                    break
                            except:
                                continue
                        
                        # URL 찾기 (여러 선택자 시도)
                        video_url = None
                        url_selectors = ["a#thumbnail", "a[href*='watch']", "a"]
                        for url_selector in url_selectors:
                            try:
                                link_element = video.find_element(By.CSS_SELECTOR, url_selector)
                                video_url = link_element.get_attribute("href")
                                if video_url and "youtube.com/watch" in video_url:
                                    print(f"URL 찾음: {video_url}")
                                    break
                            except:
                                continue
                        
                        if title and video_url:
                            new_videos_data.append({
                                "channel": channel_name,
                                "channel_url": channel_url,
                                "video_title": title,
                                "video_url": video_url,
                                "scraping_time": scraping_time
                            })
                            print(f"비디오 추가됨: {title[:30]}...")
                        else:
                            print(f"비디오 정보가 불완전함: 제목={bool(title)}, URL={bool(video_url)}")
                    except Exception as e:
                        print(f"비디오 파싱 오류: {str(e)}")
                        continue
                
                # 채널간 간격 늘림
                time.sleep(random.uniform(2, 3))
                print(f"==== {channel_name} 처리 완료 ====")
            except Exception as e:
                print(f"{channel_name} 처리 중 오류 발생: {str(e)}")
                traceback.print_exc()
                continue
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except:
            pass

    print(f"총 {len(new_videos_data)}개 비디오 데이터 수집 완료")
    update_result = update_github_jsonl(new_videos_data)
    print(f"GitHub 업데이트 {'성공' if update_result else '실패'}")


if __name__ == "__main__":
    main()
