import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import random
import requests
import shutil
from pathlib import Path
from urllib.parse import quote
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import extract_script_id, find_oldest_script_file, find_oldest_script_id  # ← 修正点

backup_script(__file__)
save_config_snapshot()

from dotenv import load_dotenv
load_dotenv()

from PIL import Image
import imagehash
from io import BytesIO

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
if not PIXABAY_API_KEY:
    raise ValueError("PixabayのAPIキーが設定されていません (.envにPIXABAY_API_KEYを追加)")

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

    return ""

def download_image(url: str, save_path: Path):
    res = requests.get(url)
    if res.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(res.content)
        print(f"✅ 画像保存: {save_path}")
    else:
        print(f"❌ 画像ダウンロード失敗: {url}")

def fetch_all_images(scene_json_path: Path, script_id: str, group_size: int = 3):
    with open(scene_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    global_tag = data.get("global_image_tag", "")
    scenes = data.get("scenes", [])

    output_dir = Path(f"data/stage_3_images/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    used_urls = set()
    used_hashes = set()

    # 3シーンごとに1枚の画像を共通使用
    for i in range(0, len(scenes), group_size):
        chunk = scenes[i:i + group_size]
        scene_ids = [scene["scene_id"] for scene in chunk]

        # チャンク内のすべてのタグを集めてゆらぎありにサンプリング
        all_tags = [tag for scene in chunk for tag in scene.get("tags", [])]
        if global_tag and global_tag != "その他":
            all_tags.insert(0, global_tag)

        # タグがなければスキップ
        if not all_tags:
            print(f"⚠️ タグが見つかりません（scene_ids: {scene_ids}）")
            continue

        selected_tags = random.sample(all_tags, min(3, len(all_tags)))

        image_url = fetch_image_url(selected_tags, used_urls, used_hashes)

        if image_url:
            print(f"[DEBUG] 使用画像URL: {image_url} → scenes: {scene_ids}")
            for scene_id in scene_ids:
                image_path = output_dir / f"{scene_id}.jpg"
                download_image(image_url, image_path)
        else:
            print(f"⚠️ 有効な画像が見つかりません: {selected_tags}")

if __name__ == "__main__":
    input_dir = Path("data/stage_2_tag")
    output_dir = Path("data/stage_3_image")

    if len(sys.argv) > 1:
        script_id = sys.argv[1]
    else:
        script_id = find_oldest_script_id(Path("scripts_done"))

    # サブディレクトリを探索し、各中にある .json ファイルを収集
    all_json_files = []
    # 修正後
    json_files = list(input_dir.glob("tags_*.json"))
    all_json_files.extend(json_files)

    # 台本IDが取れるものだけに限定
    valid_json_files = [f for f in all_json_files if extract_script_id(f.name)]
    valid_json_files.sort(key=lambda f: extract_script_id(f.name))

    if not valid_json_files:
        print("❌ 処理可能なJSONファイルが見つかりません")
        exit()

    scene_json_file = input_dir / f"tags_{script_id}.json"
    print(f"[DEBUG] script_id = {script_id}")

    if not scene_json_file.exists():
        print(f"❌ JSONファイルが見つかりません: {scene_json_file}")
        exit()

    fetch_all_images(scene_json_path=scene_json_file, script_id=script_id)
