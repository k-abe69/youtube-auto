from pathlib import Path
from datetime import datetime

def resolve_latest_script_info(base_dir="scripts_ok") -> dict:
    txt_files = list(Path(base_dir).rglob("*.txt"))
    if not txt_files:
        raise FileNotFoundError("台本が見つかりません")
    
    latest_file = max(txt_files, key=lambda p: p.stat().st_mtime)
    script_id = latest_file.stem.zfill(6)

    # 日付情報をファイルパスから抽出（例：scripts_ok/2025/05/11/000001.txt）
    parts = latest_file.parts
    year, month, day = parts[-4], parts[-3], parts[-2]

    return {
        "script_id": script_id,
        "script_path": str(latest_file),
        "date_path": f"{year}/{month}/{day}",
        "date_dir": Path(f"{year}/{month}/{day}")
    }
