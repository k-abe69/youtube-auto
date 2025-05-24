import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
import requests
import base64
import json
import time
from pathlib import Path
from common.script_utils import resolve_script_id

from dotenv import load_dotenv
load_dotenv()

# === ユーザー設定 ===
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
if not RUNWAY_API_KEY:
    raise ValueError(".envにRUNWAY_API_KEYが設定されていません")

VIDEO_MODEL_URL = "https://api.runwayml.com/v2/models/gen-4-turbo/infer"

# === 動画生成関数 ===
def generate_video_from_image(image_path: Path, output_path: Path, prompt: str):
    with open(image_path, "rb") as f:
        files = {"image": f}
        data = {
            "prompt": prompt,
            "width": 768,
            "height": 1280,
            "duration": 5,
            "fps": 24
        }
        headers = {
            "Authorization": f"Bearer {RUNWAY_API_KEY}"
        }

        response = requests.post(VIDEO_MODEL_URL, headers=headers, data=data, files=files)

    if response.status_code != 200:
        raise RuntimeError(f"❌ Runway APIエラー: {response.status_code} / {response.text}")

    result = response.json()
    video_url = result.get("video_url")
    if not video_url:
        raise ValueError("❌ 動画URLがAPIレスポンスに含まれていません")

    video_data = requests.get(video_url)
    with open(output_path, "wb") as f:
        f.write(video_data.content)
    print(f"✅ 動画保存: {output_path}")


# === メイン処理 ===
def generate_all_videos(script_id: str, prompt: str):
    image_dir = Path(f"data/stage_3_images/{script_id}")
    output_dir = image_dir  # 保存先は同じディレクトリにする
    output_dir.mkdir(parents=True, exist_ok=True)

    for image_path in sorted(image_dir.glob("*.jpg")):
        video_path = output_dir / f"{image_path.stem}.mp4"
        if video_path.exists():
            print(f"✅ 既に生成済み: {video_path}")
            continue

        try:
            print(f"🎥 生成中: {image_path.name} → {video_path.name}")
            generate_video_from_image(image_path, video_path, prompt)
            time.sleep(1.5)  # API連続呼び出しの間隔を空ける

        except Exception as e:
            print(f"❌ 動画生成失敗: {image_path.name} → {e}")


if __name__ == "__main__":
    script_id = resolve_script_id()
    with open("prompts/image/runway_prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read().strip()
    generate_all_videos(script_id, prompt)
