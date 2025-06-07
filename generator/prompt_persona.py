import os
import json
import re
from openai import OpenAI
from generator.generate_sd_image import generate_sd_image
from generator.fetch_images import upload_to_s3

openai.api_key = os.environ.get("OPENAI_API_KEY")

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
    if not tag_path.exists():
        raise FileNotFoundError(f"{tag_path} not found")
    with open(tag_path, "r", encoding="utf-8") as f:
        tags = json.load(f)
    texts = [
        item["text"] for item in tags
        if item.get("parent_scene_id") == parent_id
    ]
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
    return [generate_sd_image(prompt, negative_prompt="") for _ in range(num_images)]



def get_image_for_scene(script_id: str, parent_id: str) -> Image.Image:
    text = collect_text_for_scene(script_id, parent_id)
    return persona_pipeline(text)


def persona_pipeline(text: str):
    # ① 構図抽出
    composition = run_theme_reader(text)
    
    # ② プロンプト生成
    prompt = run_prompt_crafter(composition)

    # ③ 初期画像生成
    images = generate_image(prompt, num_images=2)

    # ④ 評価
    feedbacks = [run_image_critic(composition, "N/A") for _ in images]

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
            return images[index - 1]

    raise RuntimeError(f"Failed to parse final image selection: '{final_choice}'")


