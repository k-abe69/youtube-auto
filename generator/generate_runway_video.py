import os
from runwayml import RunwayML
from dotenv import load_dotenv
import json
from typing import List
import time
import requests  # ファイルDL用
from urllib.parse import urlparse, unquote

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common.script_utils import parse_args_script_id, get_next_script_id, mark_script_completed

import boto3
from pathlib import Path

from dotenv import load_dotenv

# .env.s3 ファイルの読み込み
dotenv_path = Path(__file__).parent.parent / ".env.s3"
load_dotenv(dotenv_path)

# 環境変数からキー情報を取得
aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
aws_region = os.environ.get("AWS_DEFAULT_REGION")  # デフォルトは東京リージョン


load_dotenv()

# 環境変数からAPIキーを取得
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

if not RUNWAY_API_KEY:
    print("エラー: RUNWAY_API_KEY 環境変数が設定されていません")
    exit()

# RunwayMLクライアントを初期化
client = RunwayML(api_key=RUNWAY_API_KEY)

def request_runway(image_url: str, image_filename: str, save_dir: Path):
    image_to_video = client.image_to_video.create(
        model="gen4_turbo",
        prompt_image=image_url,
        ratio="960:960",
        prompt_text="camera slowly panning from right to left, cinematic lighting, mysterious, a person subtly shifting posture, a person glancing sideways",
        duration=5
    )

    # タスクIDを取得
    task_id = image_to_video.id
    print("生成タスクID:", task_id)


    # 最初のステータス取得まで少し待つ
    print("⏳ 動画生成タスクの初期化を待機中...")
    time.sleep(10)  # 最初のポーリングまで10秒待機


    # タスクの状態を取得
    task = client.tasks.retrieve(task_id)

    # タスクの完了をポーリングで待機
    while task.status not in ['SUCCEEDED', 'FAILED']:
        print(f"⌛ 現在のステータス: {task.status} ... 次の確認まで10秒待機")
        time.sleep(10)
        task = client.tasks.retrieve(task_id)

    if task.status == 'SUCCEEDED':
        output = task.output
        if isinstance(output, list) and len(output) > 0 and isinstance(output[0], str):
            video_url = output[0]
            print("✅ 動画生成完了！動画URL:", video_url)

            # ローカルに保存
            output_path = save_dir / f"{Path(image_filename).stem}.mp4"
            print(f"💾 ダウンロード保存: {output_path}")
            with requests.get(video_url, stream=True) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        else:
            print("⚠ 想定外の出力形式でした。内容:", output)
    else:
        print("❌ 動画生成に失敗しました。")



def get_image_urls_for_script(script_id: str) -> List[str]:
    bucket_name = "youtube-auto-bk"
    prefix = f"stage_5_image/sd_images/{script_id}"

    if not bucket_name:
        print("エラー: AWS_S3_BUCKET_NAME 環境変数が設定されていません")
        return []

    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region,
    )

    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    if "Contents" not in response:
        print(f"⚠ 指定のパスに画像が存在しません: {prefix}")
        return []

    image_urls = []
    for obj in response["Contents"]:
        key = obj["Key"]
        if key.lower().endswith((".png", ".jpg", ".jpeg")):
            extension = os.path.splitext(key)[1].lower()
            if extension == ".png":
                content_type = "image/png"
            elif extension in [".jpg", ".jpeg"]:
                content_type = "image/jpeg"
            else:
                continue

            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': key,
                    'ResponseContentType': content_type,
                },
                ExpiresIn=3600,
            )
            image_urls.append(presigned_url)


    return image_urls

# メイン処理

# 引数として script_id を受け取る
task_name = "video"
script_id = parse_args_script_id() or get_next_script_id(task_name)
if script_id is None:
    exit()

print(f"🎬 処理対象のscript_id: {script_id}")
image_urls = get_image_urls_for_script(script_id)


save_dir = Path(f"data/stage_5_image/{script_id}")
save_dir.mkdir(parents=True, exist_ok=True)

for url in image_urls:
    # URLからファイル名を抽出
    parsed = urlparse(url)
    image_filename = Path(unquote(parsed.path)).name
    print(f"🖼️ 使用画像: {url}")
    request_runway(url, image_filename, save_dir)


# 全画像処理後に完了マーク
mark_script_completed(script_id)
print(f"✅ script_id {script_id} を完了としてマークしました")