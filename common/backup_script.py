import shutil
from datetime import datetime
from pathlib import Path

def backup_script(script_path):
    script_path = Path(script_path)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup_dir = Path("backup")
    backup_dir.mkdir(exist_ok=True)
    backup_name = f"{timestamp}_{script_path.name}"
    shutil.copy(script_path, backup_dir / backup_name)
    print(f"[OK] スクリプトバックアップ済み: {backup_dir / backup_name}")
