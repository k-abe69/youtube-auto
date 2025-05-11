import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import requests
from pathlib import Path
from urllib.parse import quote
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import resolve_latest_script_info

backup_script(__file__)
save_config_snapshot()


from dotenv import load_dotenv
load_dotenv()  # 必ずこれが getenvより前にあること


# Pixabay APIキー
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
if not PIXABAY_API_KEY:
    raise ValueError("PixabayのAPIキーが設定されていません (.envにPIXABAY_API_KEYを追加)")

# Pixabay画像を検索し、最初の結果のURLを返す
def fetch_image_url(tags: list) -> str:
    query = "+".join([quote(tag) for tag in tags])
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={query}&image_type=photo&orientation=vertical&per_page=3"
    res = requests.get(url)
    if res.status_code != 200:
        raise RuntimeError(f"Pixabayリクエスト失敗: {res.text}")
    data = res.json()
    hits = data.get("hits")
    if hits:
        return hits[0]["largeImageURL"]
    else:
        return ""

# 画像を保存する
def download_image(url: str, save_path: Path):
    res = requests.get(url)
    if res.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(res.content)
        print(f"✅ 画像保存: {save_path}")
    else:
        print(f"❌ 画像ダウンロード失敗: {url}")

# メイン処理
def fetch_all_images(scene_json_path: Path, script_id: str):
    with open(scene_json_path, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    output_dir = Path(f"images/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes:
        scene_id = scene["scene_id"]
        tags = scene["tags"]
        image_url = fetch_image_url(tags)

        if image_url:
            image_path = output_dir / f"{scene_id}.jpg"
            download_image(image_url, image_path)
        else:
            print(f"⚠️ 画像が見つかりません: {tags}")

if __name__ == "__main__":
    info = resolve_latest_script_info()
    script_id = info["script_id"]
    date_path = info["date_path"]
    scene_json_path = Path(f"data/scenes_json/{date_path}/{script_id}.json")

    fetch_all_images(scene_json_path=scene_json_path, script_id=script_id)
