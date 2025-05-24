from pathlib import Path
from datetime import datetime
import re
import sys
from typing import List, Dict
import json


def extract_script_id(filename: str) -> str:
    """
    任意のファイル名から script_id（形式: YYYYMMDD_XX） を抽出
    例:
      '20250514_01.json' → '20250514_01'
      'script_20250514_01.json' → '20250514_01'
      'audio_20250514_01.json' → '20250514_01'
    """
    match = re.search(r"(\d{8}_\d{2})", filename)
    return match.group(1) if match else None


def find_oldest_script_file(base_dir: Path) -> Path:
    """
    指定ディレクトリ内にある任意のファイル名のうち、
    script_id（形式: YYYYMMDD_XX）を含むものを抽出し、
    最も若いscript_idを持つファイルを1つ返す。
    該当しない場合は None を返す。
    """
    candidates = [
        f for f in base_dir.iterdir()
        if f.is_file() and extract_script_id(f.name) is not None
    ]
    candidates.sort(key=lambda p: extract_script_id(p.name))
    return candidates[0] if candidates else None


def find_oldest_script_id(scripts_dir: Path = Path("scripts_ok")) -> str:
    """
    scripts_okディレクトリから最も古い台本ファイルを探し、
    そのファイル名から script_id（YYYYMMDD_XX）を抽出して返す。
    """
    file = find_oldest_script_file(scripts_dir)
    if file is None:
        raise FileNotFoundError(f"📭 台本ファイルが見つかりません: {scripts_dir}")
    script_id = extract_script_id(file.name)
    if not script_id:
        raise ValueError(f"❌ script_idの抽出に失敗: {file.name}")
    return script_id

def find_newest_script_file(base_dir: Path) -> Path:
    """
    指定ディレクトリ内にある任意のファイル名のうち、
    script_id（形式: YYYYMMDD_XX）を含むものを抽出し、
    最も新しいscript_idを持つファイルを1つ返す。
    該当しない場合は None を返す。
    """
    candidates = [
        f for f in base_dir.iterdir()
        if f.is_file() and extract_script_id(f.name) is not None
    ]
    candidates.sort(key=lambda p: extract_script_id(p.name), reverse=True)
    return candidates[0] if candidates else None


def resolve_script_id():
    if len(sys.argv) > 1:
        return sys.argv[1]
    else:
        file = find_newest_script_file(Path("scripts_done"))
        if file is None:
            raise FileNotFoundError("📭 最新の台本ファイルが見つかりません")
        script_id = extract_script_id(file.name)
        if not script_id:
            raise ValueError(f"❌ script_idの抽出に失敗: {file.name}")
        return script_id


def parse_and_generate_voicevox_script(
    input_path: Path,
    script_output_path: Path,
    meta_output_path: Path
) -> None:
    """
    入力スクリプトを解析し、VOICEVOX用スクリプト（(0:00)付き）と
    各scene_id（scene_01 〜）のメタ情報を出力する。

    - [要約] は改行で分割して個別シーンにする
    - [出典] は script_output には含めず、metaには直前scene_idに紐づけて出力
    """
    with input_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    scenes = []
    current_type = None
    current_text = []
    scene_counter = 1
    last_scene_id = None

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith("[大タイトル]"):
            if current_type and current_text:
                scenes.append({"type": current_type, "text": "\n".join(current_text)})
            current_type = "main_title"
            current_text = [line.replace("[大タイトル]", "").strip()]
        elif line.startswith("[タイトル]"):
            if current_type and current_text:
                scenes.append({"type": current_type, "text": "\n".join(current_text)})
            current_type = "title"
            current_text = [line.replace("[タイトル]", "").strip()]
        elif line.startswith("[出典]"):
            if current_type and current_text:
                scenes.append({"type": current_type, "text": "\n".join(current_text)})
            current_type = "source"
            current_text = [line.replace("[出典]", "").strip()]
        elif line.startswith("[要約]"):
            if current_type and current_text:
                scenes.append({"type": current_type, "text": "\n".join(current_text)})
            current_type = "summary"
            current_text = []
        else:
            current_text.append(line)

    if current_type and current_text:
        scenes.append({"type": current_type, "text": "\n".join(current_text)})

    voicevox_lines = []
    meta = []

    for scene in scenes:
        if scene["type"] == "summary":
            for line in scene["text"].splitlines():
                line = line.strip()
                if line:
                    scene_id = f"scene_{scene_counter:02}"
                    voicevox_lines.append(f"(0:00)\n{line}\n")
                    meta.append({
                        "scene_id": scene_id,
                        "type": "summary",
                        "text": line
                    })
                    last_scene_id = scene_id
                    scene_counter += 1
        elif scene["type"] in {"title", "main_title"}:
            text = scene["text"].strip()
            if text:
                scene_id = f"scene_{scene_counter:02}"
                voicevox_lines.append(f"(0:00)\n{text}\n")
                meta.append({
                    "scene_id": scene_id,
                    "type": scene["type"],
                    "text": text
                })
                last_scene_id = scene_id
                scene_counter += 1
        elif scene["type"] == "source":
            text = scene["text"].strip()
            if text and last_scene_id:
                meta.append({
                    "scene_id": last_scene_id,  # sourceは直前sceneに紐づけ
                    "type": "source",
                    "text": text
                })

    with script_output_path.open("w", encoding="utf-8") as f:
        for line in voicevox_lines:
            f.write(line + "\n")

    with meta_output_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
