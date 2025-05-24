import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import random
import requests
import shutil
import base64
import io
import time

from PIL import Image
from pathlib import Path
from urllib.parse import quote
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import extract_script_id, find_oldest_script_file, find_oldest_script_id, resolve_script_id   # ← 修正点

backup_script(__file__)
save_config_snapshot()

from PIL import Image
import imagehash
from io import BytesIO


# 修正済み generate_sd_image
def generate_sd_image(prompt: str, negative_prompt: str, port: int = 7861) -> Image.Image:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "model": "RealisticVisionXL_v57 [49E4F2939A]",
        "width": 1024,
        "height": 1024,
        "steps": 45,
        "cfg_scale": 8.0,
        "sampler_index": "DPM++ 2M Karras",
    }

    url = f"http://127.0.0.1:{port}/sdapi/v1/txt2img"  # ✅ ここに port を反映

    response = requests.post(url, json=payload, timeout=1500)
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

def fetch_all_images(scene_json_path: Path, script_id: str, start_index: int, batch_size: int):
    with open(scene_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    output_dir = Path(f"data/stage_3_image/sd_images/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    keys = sorted(list(data.keys()))
    total = len(keys)
    batch = keys[start_index - 1:start_index - 1 + batch_size]

    negative_prompt = "nipple, areola, bare chest, exposed breasts, nsfw, ugly, deformed, lowres, blurry, text, watermark, centered composition, circular framing, tight clothes, bikini, confident pose, looking back, soft lighting, wet shirt, sideboob, elegant cleavage, seductive gaze, thigh-highs, skirt fluttering, bad anatomy, extra limbs, fused fingers, bad eyes, bad hands"

    for i, parent_id in enumerate(batch):
        prompt_data = data[parent_id]  # ← これが必要！
        prompt = prompt_data.get("prompt")
        if not prompt:
            print(f"❌ promptが存在しない: {parent_id}")
            continue

        out_path = output_dir / f"{parent_id}.png"
        if out_path.exists():
            print(f"✅ 既に生成済み: {out_path}")
            continue

        try:
            print(f"[{i+1}/{len(batch)}] Generating image for parent_id={parent_id}")
            
            start_time = time.time()
            image = generate_sd_image(prompt, negative_prompt, port=7861)

            image.save(out_path)
            duration = time.time() - start_time
            print(f"🧠 SD画像保存完了: {out_path}（{duration:.2f}秒）")
        except Exception as e:
            print(f"❌ SD画像生成失敗: {parent_id} → {type(e).__name__}: {e}")
    return start_index + batch_size < total

            

if __name__ == "__main__":
    script_id = sys.argv[1]
    start_index = int(sys.argv[2])
    batch_size = int(sys.argv[3])
    input_dir = Path("data/stage_3_prompt")
    output_dir = Path("data/stage_3_image")

    # サブディレクトリを探索し、各中にある .json ファイルを収集
    all_json_files = []
    # 修正後
    json_files = list(input_dir.glob("prompts*.json"))
    all_json_files.extend(json_files)

    # 台本IDが取れるものだけに限定
    valid_json_files = [f for f in all_json_files if extract_script_id(f.name)]
    valid_json_files.sort(key=lambda f: extract_script_id(f.name))

    if not valid_json_files:
        print("❌ 処理可能なJSONファイルが見つかりません")
        exit()

    scene_json_file = input_dir / f"prompts_{script_id}.json"
    print(f"[DEBUG] script_id = {script_id}")

    if not scene_json_file.exists():
        print(f"❌ JSONファイルが見つかりません: {scene_json_file}")
        exit()
    
    should_continue = fetch_all_images(scene_json_file, script_id, start_index, batch_size)
    sys.exit(0 if should_continue else 1)

