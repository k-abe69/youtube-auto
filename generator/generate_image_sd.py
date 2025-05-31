# セッションがリセットされたため、必要な再定義を行います
from pathlib import Path
import requests
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.script_utils import resolve_script_id


def generate_images_from_prompts(script_id: str, output_dir: Path, sd_api_url: str = "http://localhost:7860"):
    """
    指定されたscript_idのプロンプトファイルを読み込み、親シーンごとにStable Diffusionで画像を生成する。
    出力画像は output_dir に保存される。
    """
    prompt_path = Path(f"data/stage_3_prompt/prompts_{script_id}.json")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompts_data = json.load(f)

    output_dir.mkdir(parents=True, exist_ok=True)

    sd_api_url = f"http://1cwouio0ezyj96-3000.proxy.runpod.net/sdapi/v1/txt2img"

    for parent_id, content in prompts_data.items():
        prompt = content["prompt"]

        # Stable Diffusion APIへ画像生成リクエスト
        payload = {
            "prompt": prompt,
            "steps": 30,
            "width": 768,
            "height": 768,
            "sampler_name": "Euler a",
            "cfg_scale": 7
        }
        response = requests.post(sd_api_url, json=payload)
        if response.status_code != 200:
            print(f"❌ Failed to generate image for {parent_id}")
            continue

        r = response.json()
        image_data = r["images"][0]
        image_bytes = bytes.fromhex(image_data.split(",", 1)[1]) if "," in image_data else image_data.encode("latin1")

        image_path = output_dir / f"{script_id}_{parent_id}.png"
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        print(f"✅ Image saved: {image_path}")

if __name__ == "__main__":

    # メイン処理は手動実行前提（このスクリプトを.pyで保存して実行する構成）です。


    script_id = resolve_script_id()
    generate_images_from_prompts(script_id, Path(f"data/stage_4_image/{script_id}"))
