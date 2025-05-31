import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import random
import requests
import shutil
import base64
import io

from PIL import Image
from pathlib import Path
from urllib.parse import quote
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import extract_script_id, find_oldest_script_file, find_oldest_script_id, resolve_script_id   # ← 修正点

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

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
if not UNSPLASH_ACCESS_KEY:
    raise ValueError("UnsplashのAPIキーが設定されていません (.envにUNSPLASH_ACCESS_KEYを追加)")


def fetch_image_url_pixabay(tags: list, used_urls: set, used_hashes: set) -> str:
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

def fetch_image_url_unsplash(tags: list, used_urls: set, used_hashes: set) -> str:
    """
    Unsplash API を使って画像を1枚検索・検証し、有効な画像URLを返す。
    類似画像の重複は除外される。

    Parameters:
        tags (list): 検索に使うタグリスト（例: ["smile", "gentle"]）
        used_urls (set): すでに使用済みの画像URL集合（重複防止）
        used_hashes (set): すでに使用済みの画像ハッシュ集合（類似除外）

    Returns:
        str: 有効な画像URL（見つからなければ空文字）
    """
    if not UNSPLASH_ACCESS_KEY:
        raise ValueError("UnsplashのAPIキーが設定されていません (.envにUNSPLASH_ACCESS_KEYを追加)")

    # クエリ構築（空白区切り）
    query = " ".join(tags)
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": query,
        "client_id": UNSPLASH_ACCESS_KEY,
        "orientation": "portrait",         # TikTok/ショート動画向け縦型
        "content_filter": "high"           # 品質フィルター
    }

    try:
        res = requests.get(url, params=params)
        if res.status_code != 200:
            print(f"❌ Unsplashリクエスト失敗: {res.status_code} / {res.text}")
            return ""

        data = res.json()
        image_url = data.get("urls", {}).get("regular")

        if not image_url or image_url in used_urls:
            return ""
        
        # 🔁 ダウンロードイベントを送信（ポリシー必須）
        if download_location:
            try:
                requests.get(download_location, params={"client_id": UNSPLASH_ACCESS_KEY})
            except Exception as e:
                print(f"[警告] ダウンロードイベント送信失敗: {e}")


        # 類似画像のチェック（画像取得 → ハッシュ計算）
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        hash_val = imagehash.phash(img)
        is_duplicate = any(existing - hash_val <= 5 for existing in used_hashes)

        if is_duplicate:
            print(f"[SKIP] 類似画像のためスキップ: {image_url}")
            return ""

        # 使用履歴に追加
        used_urls.add(image_url)
        used_hashes.add(hash_val)
        return image_url

    except Exception as e:
        print(f"[ERROR] Unsplash画像処理中に例外: {e}")
    return ""

# 修正済み generate_sd_image
def generate_sd_image(prompt: str, negative_prompt: str, port: int = 7860) -> Image.Image:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": 512,
        "height": 768,
        "steps": 25,
        "sampler_index": "Euler a"
    }

    url = f"http://127.0.0.1:{port}/sdapi/v1/txt2img"  # ✅ ここに port を反映

    response = requests.post(url, json=payload, timeout=600)
    r = response.json()
    images = r.get("images", [])

    if not images or not images[0].strip():
        raise RuntimeError(f"No usable image returned. SD API response: {r}")

    try:
        raw_image = images[0].strip()
        base64_data = raw_image.split(",", 1)[-1] if "," in raw_image else raw_image
        decoded = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(decoded))
        image.load()
        return image
    except Exception as e:
        raise RuntimeError(f"Base64 decode or Image.open failed → {e}")


def download_image(url: str, save_path: Path):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        img = Image.open(io.BytesIO(res.content)).convert("RGB")
        img.save(save_path, format="JPEG")
        print(f"✅ 画像保存: {save_path}")
    except Exception as e:
        print(f"❌ ダウンロード失敗: {url} → {e}")

def fetch_all_images(scene_json_path: Path, script_id: str):
    with open(scene_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    global_tag = data.get("global_image_tag", "")
    scenes = data.get("scenes", [])

    output_dir = Path(f"data/stage_3_images/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    used_urls = set()
    used_hashes = set()

    # parent_scene_id ごとにまとめる
    parent_map = {}
    for scene in scenes:
        parent_id = scene["parent_scene_id"]
        parent_map.setdefault(parent_id, []).append(scene)

    # SDプロンプトファイル読み込み
    # with open(f"data/stage_2_tag/sd_{script_id}.json", "r", encoding="utf-8") as f:
    #     sd_prompts = json.load(f)

    # for i, (parent_id, prompt_data) in enumerate(sd_prompts.items()):
    #     prompt = prompt_data["prompt"]
    #     negative_prompt = prompt_data["negative_prompt"]

    #     out_dir = Path(f"data/stage_3_image/sd_images/{script_id}")
    #     out_dir.mkdir(parents=True, exist_ok=True)
    #     out_path = out_dir / f"{parent_id}.png"

    #     if out_path.exists():
    #         print(f"✅ 既に生成済み: {out_path}")
    #         continue

    #     try:
    #         print(f"[{i+1}/{len(sd_prompts)}] Generating image for parent_id={parent_id}")
    #         image = generate_sd_image(prompt, negative_prompt, port=7860)
    #         image.save(out_path)
    #         print(f"🧠 SD画像保存完了: {out_path}")
    #     except Exception as e:
    #         print(f"❌ SD画像生成失敗: {parent_id} → {type(e).__name__}: {e}")

    for parent_id, group in parent_map.items():
        # グループ内の全タグを集める
        all_tags = [tag for scene in group for tag in scene.get("tags", [])]
        if global_tag and global_tag != "その他":
            all_tags.insert(0, global_tag)

        if not all_tags:
            print(f"⚠️ タグが見つかりません（parent_scene_id: {parent_id}）")
            continue

        selected_tags = random.sample(all_tags, min(3, len(all_tags)))
        image_url = fetch_image_url_pixabay(selected_tags, used_urls, used_hashes)

        if image_url:
            print(f"[DEBUG] 使用画像URL: {image_url} → parent_scene_id: {parent_id}")
            image_path = output_dir / f"{parent_id}.jpg"
            download_image(image_url, image_path)
        else:
            print(f"⚠️ 有効な画像が見つかりません: {selected_tags} for parent_scene_id {parent_id}")


if __name__ == "__main__":
    input_dir = Path("data/stage_2_tag")
    output_dir = Path("data/stage_3_image")
    script_id = resolve_script_id()

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
