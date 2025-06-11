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
from common.script_utils import parse_args_script_id, get_next_script_id, mark_script_completed
from collections import defaultdict


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


# GPTに感情タグを問い合わせ
def detect_emotion_from_text(text: str) -> str:
    prompt_path = Path(__file__).parent / ".." / "prompts" / "image" / "emotion_prompt.txt"
    prompt = load_prompt(str(prompt_path.resolve()), {"TEXT": text})
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[感情判定エラー] {text} → {e}")
        return "neutral"

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
    parent_scene_duration = 0.0

    tagged_data = []

    for scene in timing_data:
        scene_id = scene["scene_id"]
        start_sec = scene["start_sec"]
        duration = scene["duration"]
        text = scene["text"]
        scene_type = scene.get("type", "unknown")

        force_new_parent = False

        if scene_type == "main_title":
            parent_counter = 1
            current_parent = parent_counter
            parent_scene_duration = 0.0

        elif scene_type == "title":
            force_new_parent = True

        elif parent_scene_duration + duration > 9.5:
            force_new_parent = True

        if force_new_parent:
            parent_counter += 1
            current_parent = parent_counter
            parent_scene_duration = 0.0

        parent_scene_duration += duration

        # GPT回避のためタグは空のまま
        tags = []

        tagged_data.append({
            "scene_id": scene_id,
            "start_sec": round(start_sec, 2),
            "duration": round(duration, 2),
            "text": text,
            "type": scene_type,
            "tags": tags,
            "parent_scene_id": f"{current_parent:03}"
        })

    # ✅ 親IDごとのtextをまとめる
    parent_texts = defaultdict(str)
    for scene in tagged_data:
        parent_id = scene["parent_scene_id"]
        parent_texts[parent_id] += scene["text"] + "。"

    # ✅ 各親IDごとに感情を推定
    emotion_by_parent = {}
    for parent_id, combined_text in parent_texts.items():
        emotion_by_parent[parent_id] = detect_emotion_from_text(combined_text)

    # ✅ tagged_dataに感情タグを追加
    for scene in tagged_data:
        scene["emotion"] = emotion_by_parent.get(scene["parent_scene_id"], "neutral")



    # 台本全体から共通トーン推定
    script_text = "。".join(scene["text"] for scene in timing_data)
    global_image_tag = detect_global_image_tag(script_text)

    data = {
        "global_image_tag": global_image_tag,
        "scenes": tagged_data
    }

    # ❶ 親IDごとの合計duration計算
    duration_by_parent = defaultdict(float)
    for scene in tagged_data:
        duration_by_parent[scene["parent_scene_id"]] += scene["duration"]

    # ❷ 4.9秒以上の親IDに対し _mv.txt をマークファイルとして出力
    mv_flag_dir = Path("data_long/stage_2_tag/mark_mv") / script_id
    mv_flag_dir.mkdir(parents=True, exist_ok=True)

    for parent_id, total_duration in duration_by_parent.items():
        if total_duration >= 4.9:
            mark_path = mv_flag_dir / f"{parent_id}_mv.txt"
            mark_path.write_text("MARKED")


    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # save_sd_prompts(tagged_data, script_id, output_base_dir)
    print(f"✅ タグ付きJSON出力完了: {output_path}")
    return output_path


# 実行部分（timingファイルを順に処理して scenes_json に出力）
if __name__ == "__main__":
    input_dir = Path("data_long/stage_1_audio")
    output_dir = Path("data_long/stage_2_tag")

    # ✅ script_status.jsonを見て未処理のscript_idを取得
        # ✅ task_name を指定
    task_name = "tag"
    script_id = parse_args_script_id() or get_next_script_id(task_name)
    if script_id is None:
        print("✅ 全てのスクリプトが処理済みです。")
        exit()

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
        mark_script_completed(script_id, task_name)  # ✅ 同じtask_nameを使う
    except Exception as e:
        print(f"[ERROR] 処理失敗: {timing_json} → {e}")
