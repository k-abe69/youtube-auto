import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from datetime import datetime
from dotenv import load_dotenv
import openai
import re

from pathlib import Path
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import resolve_latest_script_info
from common.global_image_tag_dict import TONE_KEYWORDS

from fugashi import Tagger  # ✅ 追加：日本語分かち書き用

backup_script(__file__)
save_config_snapshot()

# OpenAI APIキー読み込み
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# プロンプトテンプレートを読み込み、TEXTを埋め込む
def load_prompt(template_path: str, variables: dict) -> str:
    with open(template_path, "r", encoding="utf-8") as f:
        prompt = f.read()
    for key, value in variables.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)
    return prompt

# GPTにタグを問い合わせ
def generate_tags(text: str) -> list:
    prompt = load_prompt("prompts/image/tags_prompt.txt", {"TEXT": text})
    try:
        response = openai.ChatCompletion.create(
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
def tag_from_timing(timing_json_path: Path, output_base_dir: Path, script_id: str, date_path: str):
    with open(timing_json_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)

    output_dir = output_base_dir / date_path
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{script_id}.json"

    tagged_data = []
    for scene in timing_data:
        scene_id = scene["scene_id"]
        start_sec = scene["start_sec"]
        duration = scene["duration"]
        text = scene["text"]

        tags = generate_tags(text)

        tagged_data.append({
            "scene_id": scene_id,
            "start_sec": round(start_sec, 2),
            "duration": round(duration, 2),
            "text": text,
            "tags": tags
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

    print(f"✅ タグ付きJSON出力完了: {output_path}")
    return output_path

# 実行部分
if __name__ == "__main__":
    info = resolve_latest_script_info()
    script_id = info["script_id"]
    date_path = info["date_path"]
    timing_json_path = Path(f"audio/{script_id}/timing.json")

    tag_from_timing(
        timing_json_path=timing_json_path,
        output_base_dir=Path("data/scenes_json"),
        script_id=script_id,
        date_path=date_path
    )
