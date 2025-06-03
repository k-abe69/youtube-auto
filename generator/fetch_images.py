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
import argparse


from PIL import Image
from pathlib import Path
from urllib.parse import quote
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import parse_args_script_id, mark_script_completed, get_next_script_id, parse_and_generate_voicevox_script

backup_script(__file__)
save_config_snapshot()

from PIL import Image
import imagehash
from io import BytesIO

import boto3

bucket_name = "youtube-auto-bk"  # ← バケット名に置き換え


def upload_to_s3(local_path: Path, s3_path: str, bucket_name: str):
    s3 = boto3.client("s3")
    try:
        s3.upload_file(str(local_path), bucket_name, s3_path)
        print(f"✅ アップロード成功: {s3_path}")
    except Exception as e:
        print(f"❌ アップロード失敗: {s3_path} → {e}")


# 修正済み generate_sd_image
def generate_sd_image(prompt: str, negative_prompt: str, port: int = 7860) -> Image.Image:
    payload = {
        "prompt": f"{prompt}, angry",
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

    output_dir = Path(f"data/stage_5_image/sd_images/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    keys = sorted(list(data.keys()))
    total = len(keys)
    batch = keys[start_index - 1:start_index - 1 + batch_size]
    processed_any = False

    processed_count = 0
    failed_count = 0

    negative_prompt = "nipple, areola, bare chest, exposed breasts, nsfw, ugly, deformed, lowres, blurry, text, watermark, centered composition, circular framing, tight clothes, bikini, confident pose, looking back, soft lighting, wet shirt, sideboob, elegant cleavage, seductive gaze, thigh-highs, skirt fluttering, bad anatomy, extra limbs, fused fingers, bad eyes, bad hands"

    for i, parent_id in enumerate(batch):
        prompt_data = data[parent_id]  # ← これが必要！
        prompt = prompt_data.get("prompt")
        if not prompt:
            print(f"❌ promptが存在しない: {parent_id}")
            continue

        
        # 追加：mvマークファイルが存在すればファイル名を変更
        mark_mv_path = Path(f"data/stage_2_tag/mark_mv/{script_id}/{parent_id}_mv.txt")
        if mark_mv_path.exists():
            out_path = output_dir / f"{parent_id}_mv.png"
        else:
            out_path = output_dir / f"{parent_id}.png"


        if out_path.exists():
            print(f"✅ 既に生成済み: {out_path}")
            continue

        try:
            print(f"[{i+1}/{len(batch)}] Generating image for parent_id={parent_id}")
            
            start_time = time.time()
            image = generate_sd_image(prompt, negative_prompt, port=7861)

            # 生成した画像を保存し、S3にアップロード
            image.save(out_path)

            # 保存後にアップロード
            s3_path = f"stage_5_image/sd_images/{script_id}/{out_path.name}"
            upload_to_s3(out_path, s3_path, bucket_name)  # ← バケット名に置き換え

            processed_any = True
            duration = time.time() - start_time
            print(f"🧠 SD画像保存完了: {out_path}（{duration:.2f}秒）")
            processed_count += 1
        except Exception as e:
            failed_count += 1
            print(f"❌ SD画像生成失敗: {parent_id} → {type(e).__name__}: {e}")
    print(f"🟢 成功: {processed_count}件 / 🔴 失敗: {failed_count}件")
    return failed_count == 0 and processed_count > 0

            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--script_id", type=str, required=True)
    parser.add_argument("--start_index", type=int, default=1)
    parser.add_argument("--batch_size", type=int, default=3)
    args = parser.parse_args()

    script_id = args.script_id
    start_index = args.start_index
    batch_size = args.batch_size

    input_dir = Path("data/stage_3_prompt")
    output_dir = Path("data/stage_5_image")

    scene_json_file = input_dir / f"prompts_{script_id}.json"
    print(f"[DEBUG] script_id = {script_id}")

    if not scene_json_file.exists():
        print(f"❌ JSONファイルが見つかりません: {scene_json_file}")
        sys.exit(1)

    should_continue = fetch_all_images(scene_json_file, script_id, start_index, batch_size)

    sys.exit(0 if should_continue else 1)

