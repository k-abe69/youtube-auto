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

from PIL import Image
import imagehash
from io import BytesIO

# Pixabay APIキー
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
if not PIXABAY_API_KEY:
    raise ValueError("PixabayのAPIキーが設定されていません (.envにPIXABAY_API_KEYを追加)")

# Pixabay画像を検索し、類似画像を避けたURLを返す
def fetch_image_url(tags: list, used_urls: set, used_hashes: set) -> str:
    query = "+".join([quote(tag) for tag in tags])
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={query}&image_type=photo&orientation=vertical&per_page=10"
    res = requests.get(url)
    if res.status_code != 200:
        raise RuntimeError(f"Pixabayリクエスト失敗: {res.text}")
    data = res.json()
    hits = data.get("hits", [])

    for hit in hits:
        image_url = hit["largeImageURL"]
        if image_url in used_urls:
            continue

        try:
            response = requests.get(image_url)
            img = Image.open(BytesIO(response.content)).convert("RGB")
            hash_val = imagehash.phash(img)
            is_duplicate = any(existing - hash_val <= 5 for existing in used_hashes)
            if is_duplicate:
                print(f"[SKIP] 類似画像のためスキップ: {image_url}")
                continue

            used_urls.add(image_url)
            used_hashes.add(hash_val)
            return image_url
        except Exception as e:
            print(f"[ERROR] ハッシュ生成失敗: {e}")
            continue

    return ""  # 有効な画像がなければ空文字を返す

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
        data = json.load(f)

    global_tag = data.get("global_image_tag", "")
    scenes = data.get("scenes", [])

    output_dir = Path(f"images/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    used_urls = set()
    used_hashes = set()

    seen_scene_ids = set()  # 既出scene_id（大分類）を追跡

    for scene in scenes:
        full_scene_id = scene["scene_id"]         # scene_1_1
        parts = full_scene_id.split("_")
        base_scene_id = "_".join(parts[:2])  # scene_1_1 → scene_1

        if base_scene_id in seen_scene_ids:
            print(f"[SKIP] すでに画像取得済み: {base_scene_id}")
            continue
        seen_scene_ids.add(base_scene_id)

        tags = scene["tags"].copy()
        if global_tag and global_tag != "その他":
            tags.insert(0, global_tag)

        image_url = fetch_image_url(tags, used_urls, used_hashes)

        if image_url:
            print(f"[DEBUG] 使用画像URL: {image_url} （scene_id: {base_scene_id}）")
            image_path = output_dir / f"{base_scene_id}.jpg"  # 保存名は大分類ID
            download_image(image_url, image_path)
        else:
            print(f"⚠️ 有効な画像が見つかりません: {tags}")

if __name__ == "__main__":
    info = resolve_latest_script_info()
    script_id = info["script_id"]
    date_path = info["date_path"]
    scene_json_path = Path(f"data/scenes_json/{date_path}/{script_id}.json")

    fetch_all_images(scene_json_path=scene_json_path, script_id=script_id)
