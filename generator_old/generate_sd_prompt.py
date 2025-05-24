import os
import json
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import random
from dotenv import load_dotenv
from openai import OpenAI
from common.script_utils import extract_script_id, find_oldest_script_file, resolve_script_id, parse_and_generate_voicevox_script   # ← 修正ポイント



# .envファイルからOpenAI APIキーを読み込む
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 各ファイルを読み込み
with open("prompts/image/default_prompt.json", "r") as f:
    default_data = json.load(f)

with open("prompts/image/composition_prompts.json", "r") as f:
    comp_data = json.load(f)

with open("prompts/image/sd_add_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()


def call_gpt_suffix_generator(theme, scenes):
    """
    GPT APIを呼び出して、SDに追加するためのプロンプト(gpt_suffix)を生成する。
    - theme: テーマカテゴリ（例："girl"）
    - scenes: 同じ親シーンIDに属するテキスト群（例：[{scene_id, text}, ...]）
    """

    user_input = {
        "theme": theme,
        "scenes": scenes
    }

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}
        ],
        temperature=0.7
    )

    result_text = response.choices[0].message.content
    try:
        result_json = json.loads(result_text)
        return result_json["gpt_suffix"]
    except Exception as e:
        return f"Error parsing GPT output: {e}"


def generate_sd_prompt(default_data, comp_data, gpt_suffix):
    """
    SDに渡す完全なプロンプトを構成する。
    - default_prompt: カテゴリごとの基本プロンプト
    - composition_prompt: カメラ構図（距離＋角度）
    - gpt_suffix: GPTで得られた文脈ベースの追加プロンプト
    """
    # ランダムにテーマとサブカテゴリを選ぶ
    theme = random.choice(list(default_data.keys()))
    subcategory = random.choice(list(default_data[theme].keys()))
    base_prompt = default_data[theme][subcategory]

    # 各構図カテゴリから1つずつランダムに選択
    distance_prompt = random.choice(list(comp_data["distance"].values()))
    angle_prompt = random.choice(list(comp_data["angle"].values()))
    pose_prompt = random.choice(list(comp_data["pose"].values()))
    composition_prompt = random.choice(list(comp_data["composition"].values()))
    focus_prompt = random.choice(list(comp_data["focus"].values()))

    # 最終プロンプトを組み立てる
    final_prompt = f"{base_prompt}, {distance_prompt}, {angle_prompt}, {pose_prompt}, {composition_prompt}, {focus_prompt}, {gpt_suffix}"
    return final_prompt

# 上記関数を組み合わせて使えば完全なプロンプトが生成可能
# 呼び出し例（scenesをscene_jsonから渡せばOK）:
# gpt_suffix = call_gpt_suffix_generator("girl", scenes)
# full_prompt = generate_sd_prompt(default_data, comp_data, gpt_suffix)

if __name__ == "__main__":

    # 引数として script_id を受け取る
    script_id = resolve_script_id()

    # 入力ファイル読み込み
    tag_path = f"data/stage_2_tag/tags_{script_id}.json"
    output_path = f"data/stage_3_prompt/prompts_{script_id}.json"

    with open(tag_path, "r", encoding="utf-8") as f:
        tag_data = json.load(f)

    # 親シーンIDごとに処理
    parent_groups = {}
    for scene in tag_data["scenes"]:
        pid = scene["parent_scene_id"]
        parent_groups.setdefault(pid, []).append({
            "scene_id": scene["scene_id"],
            "text": scene["text"]
        })

    output = {}
    for parent_id, scenes in parent_groups.items():
        # テーマは各回ランダム選択
        theme = random.choice(list(default_data.keys()))
        gpt_suffix = call_gpt_suffix_generator(theme, scenes)
        prompt = generate_sd_prompt(default_data, comp_data, gpt_suffix)
        output[parent_id] = {
            "prompt": prompt,
            "theme": theme,
            "scenes": scenes
        }

    # 出力ファイルに保存（JSON形式）
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
