import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from datetime import datetime
from dotenv import load_dotenv
import openai
from openai import OpenAI


import re
from pathlib import Path
from shutil import move

from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.global_image_tag_dict import TONE_KEYWORDS
from fugashi import Tagger  # ✅ 追加：日本語分かち書き用
from common.script_utils import extract_script_id, find_oldest_script_id, resolve_script_id 


backup_script(__file__)
save_config_snapshot()

# OpenAI APIキー読み込み
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# プロンプトテンプレートを読み込み、TEXTを埋め込む
def load_prompt(template_path: str, variables: dict) -> str:
    with open(template_path, "r", encoding="utf-8") as f:
        prompt = f.read()
    for key, value in variables.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)
    return prompt

# GPTにタグを問い合わせ
def generate_tags(text: str) -> list:
    prompt_path = Path(__file__).parent / ".." / "prompts" / "image" / "tags_prompt.txt"
    prompt = load_prompt(str(prompt_path.resolve()), {"TEXT": text}) 
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        tag_line = response.choices[0].message.content.strip()
        tags = [tag.strip() for tag in tag_line.split("、") if tag.strip()]
        return tags
    except Exception as e:
        print(f"[タグ生成エラー] {text} → {e}")
        return ["キーワード1", "キーワード2"]

# Stable Diffusion用プロンプトをGPTで生成する
def generate_sd_prompt(scene_text: str) -> dict:
    import openai
    import json

    system_prompt = """
あなたはStable Diffusion用のプロンプト設計の専門家です。

以下の日本語のテキストは、YouTubeショート動画の「親シーン」に該当する短い台本です。
この内容の意味や雰囲気を反映した「抽象的で比喩的な背景画像」を1枚生成するために、Stable Diffusion向けのプロンプトを設計してください。

【出力フォーマット】
JSON形式で次の2項目を必ず出力してください：

{
  "prompt": "ここにSD用の英語プロンプト",
  "negative_prompt": "ここに除外する要素（英語）"
}

【制約】
- 人物や顔は原則含めずにください（抽象表現を優先）
- 映像の背景として成立するよう、過度に細かい描写やゴチャゴチャ感は避けてください
- 抽象的な感情や出来事を象徴するような構図・雰囲気を含めてください（例：孤独＝霧の街角、記憶＝崩れかけた写真、など）
- 色調は統一感を持たせ、落ち着いた雰囲気を重視してください（青・グレー・パステルなど）
- ネガティブプロンプトには必ず "realistic, human face, text, watermark, logo" を含めてください
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【入力】\n{scene_text}"}
            ],
            temperature=0.8
        )
        reply = response.choices[0].message.content.strip()
        return json.loads(reply)
    except Exception as e:
        print(f"[SDプロンプト生成エラー] → {e}")
        return {
            "prompt": "A symbolic background image",
            "negative_prompt": "realistic, human face, text, watermark, logo"
        }

# SDプロンプトを親scene単位で生成・保存する
def save_sd_prompts(scenes: list, script_id: str, output_dir: Path):
    from collections import defaultdict

    parent_map = defaultdict(list)
    for scene in scenes:
        parent_map[scene["parent_scene_id"]].append(scene)

    sd_prompts = {}
    for parent_id, group in parent_map.items():
        text = "。".join(scene["text"] for scene in group)
        sd_prompts[parent_id] = generate_sd_prompt(text)

    # 保存先
    output_path = Path("data/stage_2_tag") / f"sd_{script_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sd_prompts, f, ensure_ascii=False, indent=2)
    print(f"✅ SDプロンプト出力完了: {output_path}")


# 共通トーン判定関数（定義は変更なし）
def detect_global_image_tag(script_text: str) -> str:
    scores = {}
    for tag, keywords in TONE_KEYWORDS.items():
        score = sum(word in script_text for word in keywords)
        if score > 0:
            scores[tag] = score
    if not scores:
        return "その他"
    return max(scores.items(), key=lambda x: x[1])[0]

# 音声のtiming.jsonを読み取り、それぞれにタグを付けて出力
def tag_from_timing(timing_json_path: Path, output_base_dir: Path):
    with open(timing_json_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)

    # ファイル名から script_id（basename）と date_path を抽出
    script_id = timing_json_path.stem.replace("timing_", "")
    output_path = output_base_dir / f"tags_{script_id}.json"

    # ✅ 保存先ディレクトリが存在しなければ作成
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parent_counter = 1
    current_parent = parent_counter
    group_counter = 0  # タイトル＋要約合わせたカウント

    tagged_data = []

    for scene in timing_data:
        scene_id = scene["scene_id"]
        start_sec = scene["start_sec"]
        duration = scene["duration"]
        text = scene["text"]
        scene_type = scene.get("type", "unknown")

        if scene_type == "main_title":
            parent_counter = 1
            current_parent = parent_counter
            group_counter = 0

        elif scene_type == "title":
            parent_counter += 1
            current_parent = parent_counter
            group_counter = 1  # タイトル自体を1件目と数える

        elif scene_type == "summary":
            group_counter += 1
            if group_counter > 3:
                parent_counter += 1
                current_parent = parent_counter
                group_counter = 1  # このsummaryを新グループの1件目としてカウント

        # sourceなどはgroup_counterに影響しない

        tags = generate_tags(text)

        tagged_data.append({
            "scene_id": scene_id,
            "start_sec": round(start_sec, 2),
            "duration": round(duration, 2),
            "text": text,
            "type": scene_type,
            "tags": tags,
            "parent_scene_id": f"{current_parent:03}"
        })


    # 台本全体から共通トーン推定
    script_text = "。".join(scene["text"] for scene in timing_data)
    global_image_tag = detect_global_image_tag(script_text)

    data = {
        "global_image_tag": global_image_tag,
        "scenes": tagged_data
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # save_sd_prompts(tagged_data, script_id, output_base_dir)
    print(f"✅ タグ付きJSON出力完了: {output_path}")
    return output_path


# 実行部分（timingファイルを順に処理して scenes_json に出力）
if __name__ == "__main__":
    input_dir = Path("data/stage_1_audio")
    output_dir = Path("data/stage_2_tag")

    # ✅ script_idを引数から取得、なければ自動取得
    script_id = resolve_script_id()


    timing_json = input_dir / script_id / f"timing_{script_id}.json"
    if not timing_json.exists():
        print(f"❌ timingファイルが見つかりません: {timing_json}")
        exit()
 
    date_path = timing_json.parent.name
    out_path = output_dir / f"tags_{script_id}.json"
    if out_path.exists():
        print(f"⚠️ 既に処理済み: {out_path}")
        exit()

    try:
        tag_from_timing(timing_json_path=timing_json, output_base_dir=output_dir)
    except Exception as e:
        print(f"[ERROR] 処理失敗: {timing_json} → {e}")
