import os
import json
import re
from openai import OpenAI
# 修正後（ワークスペースルートに `sys.path` を通してある前提）
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image
from pathlib import Path
import requests
import base64
import io


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

PROMPT_DIR = "prompts/image/prompt_generator/"

def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def call_gpt(user_prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def collect_text_for_scene(script_id, parent_id):
    tag_path = Path(f"data/stage_2_tag/tags_{script_id}.json")
    print(f"📂 読み込み対象: {tag_path}")

    if not tag_path.exists():
        raise FileNotFoundError(f"{tag_path} not found")

    with open(tag_path, "r", encoding="utf-8") as f:
        tags = json.load(f)
        print(f"📦 読み込み型: {type(tags)}")
        if isinstance(tags, list):
            print(f"📄 件数: {len(tags)}")
        else:
            print(f"⚠️ 想定外のデータ: {str(tags)[:100]}")

    texts = [
        item["text"] for item in tags
        if isinstance(item, dict) and item.get("parent_scene_id") == parent_id
    ]

    print(f"📝 抽出されたテキスト数: {len(texts)}")
    return "\n".join(texts)

def run_theme_reader(input_text: str) -> str:
    template = load_prompt_template("ThemeRader.txt")
    user_prompt = template.replace("「{input_text}」", input_text)
    return call_gpt(user_prompt)


def run_prompt_crafter(composition: str) -> str:
    template = load_prompt_template("PromptCrafter.txt")
    user_prompt = template.replace("「{composition}」", composition)
    return call_gpt(user_prompt)


def run_image_critic(composition: str, image_info: str) -> str:
    template = load_prompt_template("ImageCritic.txt")
    user_prompt = (
        template
        .replace("「{composition}」", composition)
        .replace("「{image_info}」", image_info)
    )
    return call_gpt(user_prompt)


def run_image_improver(original_prompt: str, composition: str, feedback: str) -> str:
    template = load_prompt_template("ImageImprover.txt")
    user_prompt = (
        template
        .replace("「{original_prompt}」", original_prompt)
        .replace("「{composition}」", composition)
        .replace("「{feedback}」", feedback)
    )
    return call_gpt(user_prompt)


def run_finalizer(composition: str, image_list: list[str], feedbacks: list[str]) -> str:
    template = load_prompt_template("Finalizer.txt")
    image_block = "\n".join([f"{i+1}: {img}" for i, img in enumerate(image_list)])
    feedback_block = "\n".join([f"{i+1}: {fb}" for i, fb in enumerate(feedbacks)])

    user_prompt = (
        template
        .replace("「{composition}」", composition)
        .replace("「{image_list}」", image_block)
        .replace("「{feedbacks}」", feedback_block)
    )
    return call_gpt(user_prompt)

def generate_image(prompt: str, num_images: int = 1) -> list[Image.Image]:
    results = []
    for i in range(num_images):
        try:
            img = generate_sd_image(prompt, negative_prompt="")
            results.append(img)
        except Exception as e:
            print(f"❌ 画像生成に失敗（{i+1}/{num_images}）: {e}")
            raise  # ← ここで必ず止める
    return results
# 修正済み generate_sd_image
def generate_sd_image(prompt: str, negative_prompt: str, port: int = 7860) -> Image.Image:
    

    print("✅ generate_sd_image に入った")

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

    try:
        response = requests.post(url, json=payload, timeout=1500)
        print("🔵 レスポンスステータス:", response.status_code)
        print("🔵 レスポンステキスト:", response.text[:500])  # 長すぎる場合の対策

        r = response.json()
        print("🔵 JSON型:", type(r))

        if not isinstance(r, dict):
            raise TypeError(f"JSON expected dict but got: {type(r)}\n内容: {r}")

        images = r.get("images", [])
    except Exception as e:
        raise RuntimeError(f"🚨 SD API呼び出し or JSON解析に失敗 → {e}")

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

def get_image_for_scene(script_id: str, parent_id: str) -> Image.Image:
    print(f"🚩 get_image_for_scene CALLED with script_id={script_id}, parent_id={parent_id}")
    try:
        text = collect_text_for_scene(script_id, parent_id)
        print(f"📝 collected text: {text[:50]}...")  # 長い場合用に省略
        image = persona_pipeline(text)
        print("✅ persona_pipeline completed:", type(image))
        if not isinstance(image, Image.Image):
            raise TypeError(f"persona_pipeline did not return an Image: got {type(image)}")

        return image
    except Exception as e:
        print(f"💥 get_image_for_scene exception: {type(e).__name__}: {e}")
        raise  # 上位の try に渡す


def persona_pipeline(text: str):
    print("① 構図抽出 開始")
    composition = run_theme_reader(text)
    print("① 構図抽出 完了:", composition)

    print("② プロンプト生成 開始")
    prompt = run_prompt_crafter(composition)
    print("② プロンプト生成 完了:", prompt)

    print("③ 初期画像生成 開始")
    images = generate_image(prompt, num_images=2)
    print("✅ 画像生成後の型:", [type(img) for img in images])

    # ④ 評価
    feedbacks = [run_image_critic(composition, "N/A") for _ in images]
    print("✅ 画像生成後の型:", [type(img) for img in images])

    # ⑤ 改善プロンプト作成
    improved_prompt = run_image_improver(prompt, composition, feedbacks[0])

    # ⑥ 再生成
    improved = generate_image(improved_prompt, num_images=1)
    images += improved
    feedbacks = [run_image_critic(composition, "N/A") for _ in images]

    # ⑦ 最終選定
    final_choice = run_finalizer(composition, [f"Image {i+1}" for i in range(len(images))], feedbacks)

    # 選定された画像を返す
    match = re.search(r'\d+', final_choice)
    if match:
        index = int(match.group())
        if 1 <= index <= len(images):
            if isinstance(images[index - 1], Image.Image):
                return images[index - 1]
            else:
                raise TypeError(f"Final selection is not an image: {type(images[index - 1])}")
        else:
            raise RuntimeError(f"Failed to parse final image selection: '{final_choice}'")
