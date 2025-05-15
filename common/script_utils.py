from pathlib import Path
from datetime import datetime
import re

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
