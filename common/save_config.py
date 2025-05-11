import shutil
import os
from datetime import datetime

def save_config_snapshot(config_path="config/config.json"):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup_path = f"config/versions/{timestamp}_config.json"
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy(config_path, backup_path)
    print(f"[OK] config.jsonをバックアップしました: {backup_path}")
