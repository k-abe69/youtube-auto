from pathlib import Path
from datetime import datetime
import re
import sys
from typing import List, Dict, Union
import json
import os
import argparse




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

ROOT_DIR = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT_DIR / "script_status.json"

def get_next_script_id(task_name: str, status_path="script_status.json", explicit_script_id: str = None):

    DEPENDENCIES = {
        "audio": [],
        "tag": ["audio"],
        "prompt": ["tag"],
        "subtitle": ["prompt"],
        "image": ["subtitle"],
        "video": ["audio", "image", "subtitle"],
        "compose": ["subtitle"]
    }

    status_path = Path(ROOT_DIR) / status_path  # ← ここで Path に変換

    all_completed = []
    unmet_dependencies = []
    if not status_path.exists():
        print("⚠️ statusファイルが存在しません")
        return None

    with open(status_path, encoding="utf-8") as f:
        status_data = json.load(f)

    # 明示的にscript_idが指定されている場合、そのstatusを検証して即返す
    if explicit_script_id:
        status = status_data.get(explicit_script_id, {})
        unmet = [dep for dep in DEPENDENCIES[task_name] if status.get(dep) != True]
        if unmet:
            # print(f"[⛔] 依存未達: {explicit_script_id}（未完了: {unmet}）")
            return None
        if status.get(task_name) == True:
            # print(f"[✓] すでに完了: {explicit_script_id} → {task_name}")
            return None
        print(f"[INFO] 明示された処理対象: {explicit_script_id}（task: {task_name}）")
        return explicit_script_id

    for script_id, status in status_data.items():
        # print(f"[DEBUG] status_path = {status_path}")
        # print(f"[DEBUG] checking: {script_id}, task={task_name}, status={status}")

        # すでに完了していたらスキップ
        if status.get(task_name) == True:
            all_completed.append(script_id)
            continue

        # 依存タスクが未完了ならスキップ
        unmet = [dep for dep in DEPENDENCIES[task_name] if status.get(dep) != True]
        if unmet:
            # print(f"[⛔] 依存未達: {script_id}（未完了: {unmet}）")
            unmet_dependencies.append(script_id)
            continue  # OK: スキップして次の script_id を探す
        print(f"[INFO] 処理対象: {script_id}（task: {task_name}）")
        return script_id

    # ログ出力：依存未達と完了済みを区別して表示
    if all_completed and not unmet_dependencies:
        print(f"[✓] task={task_name} に対する処理対象はすべて完了済みです。")
    elif unmet_dependencies and not all_completed:
        print(f"[⏳] task={task_name} に対する処理対象はすべて依存タスク未完了のためスキップされました。")
    elif not all_completed and not unmet_dependencies:
        print(f"[❌] task={task_name} に該当する台本が存在しません。")
    else:
        print(f"[INFO] task={task_name} に対する処理対象は現在ありません。")

    return None


def mark_script_completed(script_id: str, task_name: str, status_path="script_status.json"):
    status_path = Path(ROOT_DIR) / status_path  # 最初に Path 化＋ルート指定
    status_data = load_status_data(status_path)

    if not status_path.exists():
        print("⚠️ statusファイルが存在しません")
        return

    with open(status_path, encoding="utf-8") as f:
        status_data = json.load(f)

    status_data.setdefault(script_id, {})[task_name] = True

    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 完了フラグ更新: {script_id} → {task_name}=True")


def load_status_data(path: Union[str, Path] = STATUS_PATH):
    path = Path(path)
    if not path.exists():
        print(f"⚠️ statusファイルが存在しません: {path}")
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args_script_id():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script_id", type=str, required=False)
    args, _ = parser.parse_known_args()
    return args.script_id
