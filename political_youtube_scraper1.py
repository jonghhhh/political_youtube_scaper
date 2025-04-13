import requests
import re
import json
import time
import os
import sys
import random
import base64
from datetime import datetime, timezone, timedelta
from github import Github, GithubException

def extract_videos_info(channel_info):
    """YouTube 채널에서 최대 5개의 비디오 정보를 추출하는 함수"""
    channel_name = channel_info["channel"]
    channel_url = channel_info["channel_url"]
    
    # 현재 시간 (UTC)를 서울 시간으로 변환 (UTC+9)
    utc_now = datetime.now(timezone.utc)
    seoul_now = utc_now.astimezone(timezone(timedelta(hours=9)))
    scraping_time = seoul_now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 기본 헤더 설정
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    videos_info = []
    
    try:
        # GET 요청 보내기
        print(f"'{channel_name}'의 URL에 접속 중: {channel_url}")
        response = requests.get(channel_url, headers=headers)
        
        if response.status_code == 200:
            html_content = response.text
            
            # YouTube 데이터 추출 패턴
            patterns = [
                r'var\s+ytInitialData\s*=\s*({.+?});</script>',
                r'window\["ytInitialData"\]\s*=\s*({.+?});</script>',
                r'ytInitialData\s*=\s*({.+?});</script>'
            ]
            
            json_data = None
            for pattern in patterns:
                match = re.search(pattern, html_content, re.DOTALL)
                if match:
                    try:
                        json_data = json.loads(match.group(1))
                        break
                    except json.JSONDecodeError as e:
                        print(f"JSON 파싱 오류 (패턴 '{pattern}'): {e}")
                        continue
            
            if not json_data:
                print(f"'{channel_name}' 채널에서 YouTube 데이터를 찾을 수 없습니다.")
                return []
            
            # 스트림 페이지인지 확인
            is_stream_page = '/streams' in channel_url
            
            # 탭 구조 찾기
            tabs = json_data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            
            for tab in tabs:
                if "tabRenderer" not in tab:
                    continue
                
                tab_renderer = tab["tabRenderer"]
                tab_title = tab_renderer.get("title", "")
                
                # 적절한 탭 찾기
                if is_stream_page:
                    if not (tab_title in ["실시간 스트림", "라이브", "LIVE", "STREAMS", "Streams"]):
                        continue
                else:
                    if not (tab_title in ["동영상", "VIDEOS", "Videos"]):
                        continue
                
                if "content" not in tab_renderer:
                    continue
                
                content = tab_renderer["content"]
                
                # 리치 그리드 렌더러 (표준 비디오 레이아웃)
                if "richGridRenderer" in content:
                    grid_items = content["richGridRenderer"].get("contents", [])
                    
                    for item in grid_items:
                        if "richItemRenderer" not in item:
                            continue
                        
                        rich_content = item["richItemRenderer"].get("content", {})
                        
                        if "videoRenderer" in rich_content:
                            video_renderer = rich_content["videoRenderer"]
                        else:
                            continue
                        
                        # 제목 추출
                        title = ""
                        title_runs = video_renderer.get("title", {}).get("runs", [])
                        if title_runs:
                            title = "".join([run.get("text", "") for run in title_runs])
                        
                        # 비디오 ID 추출
                        video_id = video_renderer.get("videoId", "")
                        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                        
                        # 길이 추출
                        length_text = ""
                        length_obj = video_renderer.get("lengthText", {})
                        if "simpleText" in length_obj:
                            length_text = length_obj["simpleText"]
                        elif "runs" in length_obj:
                            length_text = "".join([run.get("text", "") for run in length_obj["runs"]])
                        
                        # 조회수 추출
                        view_count = ""
                        view_obj = video_renderer.get("viewCountText", {})
                        if "simpleText" in view_obj:
                            view_count = view_obj["simpleText"]
                        elif "runs" in view_obj:
                            view_count = "".join([run.get("text", "") for run in view_obj["runs"]])
                        
                        # 비디오 정보 저장
                        if title and video_url:
                            video_info = {
                                "channel": channel_name,
                                "channel_url": channel_url,
                                "title": title,
                                "length": length_text,
                                "views": view_count,
                                "video_url": video_url,
                                "scraping_time": scraping_time
                            }
                            
                            videos_info.append(video_info)
                            print(f"비디오 추가: {title[:30]}...")
                        
                        # 5개만 추출
                        if len(videos_info) >= 5:
                            break
                    
                # 비디오 섹션 렌더러 (대체 레이아웃)
                elif "sectionListRenderer" in content:
                    sections = content["sectionListRenderer"].get("contents", [])
                    
                    for section in sections:
                        if "itemSectionRenderer" not in section:
                            continue
                        
                        items = section["itemSectionRenderer"].get("contents", [])
                        
                        for item in items:
                            # 비디오 렌더러 찾기
                            video_renderer = None
                            
                            if "videoRenderer" in item:
                                video_renderer = item["videoRenderer"]
                            elif "shelfRenderer" in item:
                                # 쉘프 렌더러 내부의 비디오 확인
                                shelf = item["shelfRenderer"]
                                if "content" in shelf and "horizontalListRenderer" in shelf["content"]:
                                    for item_list in shelf["content"]["horizontalListRenderer"].get("items", []):
                                        if "gridVideoRenderer" in item_list:
                                            video_renderer = item_list["gridVideoRenderer"]
                            
                            if not video_renderer:
                                continue
                            
                            # 제목 추출
                            title = ""
                            title_runs = video_renderer.get("title", {}).get("runs", [])
                            if title_runs:
                                title = "".join([run.get("text", "") for run in title_runs])
                            
                            # 비디오 ID 추출
                            video_id = video_renderer.get("videoId", "")
                            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                            
                            # 길이 추출
                            length_text = ""
                            length_obj = video_renderer.get("lengthText", {})
                            if "simpleText" in length_obj:
                                length_text = length_obj["simpleText"]
                            elif "runs" in length_obj:
                                length_text = "".join([run.get("text", "") for run in length_obj["runs"]])
                            
                            # 조회수 추출
                            view_count = ""
                            view_obj = video_renderer.get("viewCountText", {})
                            if "simpleText" in view_obj:
                                view_count = view_obj["simpleText"]
                            elif "runs" in view_obj:
                                view_count = "".join([run.get("text", "") for run in view_obj["runs"]])
                            
                            # 비디오 정보 저장
                            if title and video_url:
                                video_info = {
                                    "channel": channel_name,
                                    "channel_url": channel_url,
                                    "title": title,
                                    "length": length_text,
                                    "views": view_count,
                                    "video_url": video_url,
                                    "scraping_time": scraping_time
                                }
                                
                                videos_info.append(video_info)
                                print(f"비디오 추가: {title[:30]}...")
                            
                            # 5개만 추출
                            if len(videos_info) >= 5:
                                break
                        
                        # 충분한 비디오를 찾았으면 중단
                        if len(videos_info) >= 5:
                            break
        else:
            print(f"오류 발생: '{channel_name}' 채널 접근 실패 (상태 코드: {response.status_code})")
    
    except Exception as e:
        print(f"오류 발생: '{channel_name}' 채널 처리 중 예외 - {str(e)}")
    
    return videos_info

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
            except Exception as e:
                print(f"파일 읽기 오류: {str(e)}")
                return [], contents.sha
        else:
            return [], contents.sha
    except GithubException as e:
        if e.status == 404:
            return [], None
        else:
            print(f"GitHub 예외: {e.status} - {e.data}")
            return [], None
    except Exception as e:
        print(f"예외 발생: {str(e)}")
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
        print("새로운 데이터가 없습니다. GitHub 업데이트를 건너뜁니다.")
        return True

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("GITHUB_TOKEN 환경 변수가 설정되지 않았습니다.")
        return False

    # 아래 repo_name과 file_path는 사용 환경에 맞게 수정하세요.
    repo_name = "jonghhhh/political_youtube_scaper"
    file_path = "youtube_videos.jsonl"

    try:
        # 서울 시간으로 커밋 메시지 생성
        seoul_timezone = timezone(timedelta(hours=9))
        seoul_time = datetime.now(seoul_timezone)
        
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        existing_data, sha = safe_read_jsonl_file(repo, file_path)
        
        print(f"GitHub에서 {len(existing_data)}개의 기존 데이터를 불러왔습니다.")
        
        combined_data = existing_data + new_data

        # video_url 기준 deduplication (최신 scraping_time 데이터만 남김)
        deduped_records = {}
        for record in combined_data:
            url = record.get("video_url", "")
            if url:
                existing_time = deduped_records.get(url, {}).get("scraping_time", "")
                current_time = record.get("scraping_time", "")
                
                if (url not in deduped_records) or (current_time > existing_time):
                    deduped_records[url] = record

        jsonl_content = convert_to_jsonl(list(deduped_records.values()))
        commit_message = f"Update videos data at {seoul_time.strftime('%Y-%m-%d %H:%M:%S')} KST"
        
        if sha:
            repo.update_file(file_path, commit_message, jsonl_content, sha)
        else:
            repo.create_file(file_path, commit_message, jsonl_content)
            
        print(f"GitHub 업데이트 완료: {len(new_data)}개 항목 추가, 총 {len(deduped_records)}개 항목 유지됨")
        return True
    except Exception as e:
        print(f"GitHub 업데이트 실패: {str(e)}")
        return False

def main():
    # 채널 목록
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
    
    # 서울 시간대 출력
    seoul_tz = timezone(timedelta(hours=9))
    now_seoul = datetime.now(seoul_tz)
    print(f"스크래핑 시작 (서울 시간): {now_seoul.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 모든 비디오 정보 저장 리스트
    all_videos = []
    channel_counts = {}
    
    # 채널별 처리
    for i, channel in enumerate(channels, 1):
        channel_name = channel["channel"]
        print(f"\n[{i}/{len(channels)}] '{channel_name}' 채널 처리 중...")
        
        # 비디오 정보 추출
        videos = extract_videos_info(channel)
        
        # 채널별 수집 개수 기록
        channel_counts[channel_name] = len(videos)
        
        # 전체 비디오 목록에 추가
        all_videos.extend(videos)
        
        # 마지막 채널이 아니면 대기 (너무 많은 요청 방지)
        if i < len(channels):
            wait_time = random.uniform(2, 4)  # 2-4초 랜덤 대기
            print(f"다음 채널 처리 전 {wait_time:.1f}초 대기 중...")
            time.sleep(wait_time)
    
    # 결과 요약
    print(f"\n총 {len(all_videos)}개 비디오 수집 완료")
    
    print("\n채널별 수집 비디오 수:")
    for channel, count in channel_counts.items():
        print(f"- {channel}: {count}개")
    
    # 로컬 JSONL 파일 저장 (백업용)
    with open("youtube_videos_local.jsonl", "w", encoding="utf-8") as f:
        for video in all_videos:
            f.write(json.dumps(video, ensure_ascii=False) + "\n")
    
    # GitHub 업데이트
    update_github_jsonl(all_videos)

if __name__ == "__main__":
    main()
