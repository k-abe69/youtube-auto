import os
import json
import pickle
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from moviepy.editor import VideoFileClip
import time
from googleapiclient.errors import HttpError


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.script_utils import get_next_script_id, mark_script_completed  # 追加


# 認証とYouTube APIのスコープ
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = f"youtube_upload/client_secret.json"
TOKEN_FILE = f"token.json"

def authenticate_youtube():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def extract_main_title(meta_file_path):
    with open(meta_file_path, encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        if item.get("type") == "main_title":
            title = item.get("text", "").replace("\n", "")
            if "#shorts" not in title.lower():
                title += " #shorts"
            return title
    raise ValueError("main_title が見つかりませんでした。")

def upload_video(youtube, video_path, title, tags=None, privacy_status="unlisted", publish_at=None):
    body = {
        "snippet": {
            "title": title,
            "description": (
                "毎日雑学ショート動画を投稿中！\n"
                "ぜひチャンネル登録・高評価お願いします！\n"
                "#雑学 #ショート動画 #shorts"
            ),
            "categoryId": "22",  # People & Blogs
            "tags": tags or []
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy_status,
        }
    }

    if publish_at:
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response.get("id")

def get_next_available_slot(schedule_file: str = "youtube_upload/schedule.json", max_days=90):
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    # ファイルがなければ初期化 ★修正
    if not os.path.exists(schedule_file) or os.path.getsize(schedule_file) == 0:
        with open(schedule_file, "w", encoding="utf-8") as f:
            json.dump([], f)

    # 読み込み（空ファイル対応） ★修正
    try:
        with open(schedule_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            reserved = set(json.loads(content)) if content else set()
    except Exception:
        reserved = set()

    # スロット探索
    for day in range(max_days):
        base = (now + timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
        for hour in [18, 21]:
            slot = base.replace(hour=hour)
            if slot <= now:
                continue
            slot_iso = slot.astimezone(timezone.utc).isoformat()
            if slot_iso not in reserved:
                return slot_iso

    raise RuntimeError("⚠️ 空きスロットが max_days 先まで見つかりません")

def mark_slot_reserved(slot_iso: str, schedule_file: str = "youtube_upload/schedule.json"):
    
    # 初期化 ★修正
    if not os.path.exists(schedule_file):
        with open(schedule_file, "w", encoding="utf-8") as f:
            json.dump([], f)

    try:
        with open(schedule_file, "r", encoding="utf-8") as f:
            reserved = json.load(f)
    except FileNotFoundError:
        reserved = []

    reserved.append(slot_iso)
    reserved = sorted(list(set(reserved)))  # 重複排除
    with open(schedule_file, "w", encoding="utf-8") as f:
        json.dump(reserved, f, indent=2)

def extract_thumbnail(video_path: str, output_path: str, time_sec: float = 0.5):
    clip = VideoFileClip(str(video_path))  # ←ここ

    frame = clip.get_frame(time_sec)  # 指定秒のフレームを取得
    clip.close()

    # 画像として保存
    from PIL import Image
    image = Image.fromarray(frame)
    image.save(str(output_path))           # ←ここ

def set_thumbnail_with_retry(youtube, video_id: str, thumbnail_path: str, retries: int = 5):
    media = MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
    for i in range(retries):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
            print("✅ サムネイル設定成功")
            return
        except HttpError as e:
            print(f"⚠️ サムネイル設定失敗（{i+1}回目）: {e}")
            time.sleep(5)  # 5秒待ってリトライ
    print("❌ サムネイル設定失敗（リトライ終了）")

def main():
    task_name = "upload"
    youtube = authenticate_youtube()
    while True:

        script_id = get_next_script_id(task_name)
        if not script_id:
            print("✅ アップロード対象がありません。")
            return

        base_dir = Path(f"data/stage_6_output/{script_id}")
        video_path = base_dir / "final.mp4"
        meta_path = Path(f"data/stage_1_audio/{script_id}/script_meta_{script_id}.json")


        if not video_path.exists():
            print(f"❌ 動画ファイルが存在しません: {video_path}")  # ★修正
            return

        title = extract_main_title(meta_path)
        # 予約投稿のスロット決定
        publish_at = get_next_available_slot()  # UTC ISO文字列を取得

        success = False  # ← 追加
        try:
            video_id = upload_video(
                youtube,
                str(video_path),
                title=title,
                tags=["雑学", "知識", "教育", "科学", "社会", "ショート動画", "shorts", "Trivia"],
                publish_at=publish_at,
            )
            success = True
        except Exception as e:
            print(f"❌ アップロード失敗: {e}")
            return

        extract_thumbnail(base_dir / "final.mp4", base_dir / "thumbnail.jpg")
        # サムネイル設定
        set_thumbnail_with_retry(youtube, video_id, str(base_dir / "thumbnail.jpg"))

        if success:
            mark_slot_reserved(publish_at)  # ★修正

        print(f"✅ アップロード完了: https://youtu.be/{video_id}")
        mark_script_completed(script_id, task_name)  # 完了フラグ更新

if __name__ == "__main__":
    main()