import os
import json
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import random
from dotenv import load_dotenv
from openai import OpenAI
from common.script_utils import parse_args_script_id, get_next_script_id, mark_script_completed



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

with open("prompts/image/human_composition_prompts.json", "r") as f:
    human_comp_data = json.load(f)

with open("prompts/image/emotion_suffix.json", "r", encoding="utf-8") as f:
    emotion_suffix_data = json.load(f)


# def call_gpt_suffix_generator(theme, scenes):
#     """
#     GPT APIを呼び出して、SDに追加するためのプロンプト(gpt_suffix)を生成する。
#     - theme: テーマカテゴリ（例："girl"）
#     - scenes: 同じ親シーンIDに属するテキスト群（例：[{scene_id, text}, ...]）
#     """

#     user_input = {
#         "theme": theme,
#         "scenes": scenes
#     }

#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}
#         ],
#         temperature=0.7
#     )

#     result_text = response.choices[0].message.content
#     try:
#         result_json = json.loads(result_text)
#         return result_json["gpt_suffix"]
#     except Exception as e:
#         return f"Error parsing GPT output: {e}"


def generate_sd_prompt(theme, default_data, comp_data, human_comp_data, gpt_suffix):
    subcategory = random.choice(list(default_data[theme].keys()))
    base_prompt = default_data[theme][subcategory]

    # 人間系テーマの場合はhuman_comp_dataを使用
    if theme in ["girl", "beauty", "normal_beauty"]:
        cdata = human_comp_data
    else:
        cdata = comp_data

    distance_prompt = random.choice(list(cdata["distance"].values()))
    angle_prompt = random.choice(list(cdata["angle"].values()))
    pose_prompt = random.choice(list(cdata["pose"].values()))
    composition_prompt = random.choice(list(cdata["composition"].values()))
    focus_prompt = random.choice(list(cdata["focus"].values()))

    final_prompt = f"{base_prompt}, {distance_prompt}, {angle_prompt}, {pose_prompt}, {composition_prompt}, {focus_prompt}, {gpt_suffix}"
    return final_prompt

if __name__ == "__main__":

    # 引数として script_id を受け取る
    task_name = "prompt"
    script_id = parse_args_script_id() or get_next_script_id(task_name)
    if script_id is None:
        exit()

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

        # 出現比率の設定
        weighted_theme_choices = (
            ["girl"] * 1 +               # 10%
            ["beauty"] * 1 +             # 10%
            ["animal"] * 1 +             # 10%
            ["scenery"] * 1 +            # 10%
            ["normal_beauty"] * 6        # 60%
        )

        # テーマを確率に基づいて選択
        theme = random.choice(weighted_theme_choices)

        # 感情のタグを取得（なければ None）
        emotion_tag = None
        for scene in scenes:
            if "emotion" in scene:
                emotion_tag = scene["emotion"]
                break

        # テーマが人間系なら感情テンプレを付加
        gpt_suffix = ""
        if theme in ["girl", "beauty", "normal_beauty"] and emotion_tag in emotion_suffix_data:
            gpt_suffix = emotion_suffix_data[emotion_tag]

        prompt = generate_sd_prompt(theme, default_data, comp_data, human_comp_data, gpt_suffix)

        output[parent_id] = {
            "prompt": prompt,
            "theme": theme,
            "scenes": scenes
        }

    # 出力ファイルに保存（JSON形式）
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    mark_script_completed(script_id, task_name)

