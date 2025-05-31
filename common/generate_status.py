import os
import re
import json
from datetime import datetime

SCRIPTS_DIR = "scripts"
STATUS_FILE = "script_status.json"
FILENAME_PATTERN = r"script_(\d{8})_(\d{3})\.txt"

# ステータスの初期構造
INITIAL_STATUS = {
    "audio": "pending",
    "tag": "pending",
    "prompt": "pending",
    "subtitle": "pending",
    "image": "pending",
    "video": True,
    "compose": "pending"
}

# ファイル一覧取得
files = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".txt")]
existing_scripts = [f for f in files if re.match(FILENAME_PATTERN, f)]
unnamed_scripts = [f for f in files if not re.match(FILENAME_PATTERN, f)]

# 更新日時順に並び替え
unnamed_scripts.sort(key=lambda f: os.path.getmtime(os.path.join(SCRIPTS_DIR, f)))

# 既存スクリプトIDを抽出
existing_ids = set()
for fname in existing_scripts:
    match = re.match(FILENAME_PATTERN, fname)
    if match:
        script_id = f"{match.group(1)}_{match.group(2)}"
        existing_ids.add(script_id)

# リネーム処理
renamed_files = []
date_to_count = {}

for fname in unnamed_scripts:
    fpath = os.path.join(SCRIPTS_DIR, fname)
    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
    date_str = mtime.strftime("%Y%m%d")

    # 同日付で既存ファイルの最大番号を確認
    same_day_files = [f for f in existing_scripts if f.startswith(f"script_{date_str}")]
    count = len(same_day_files) + date_to_count.get(date_str, 0) + 1
    date_to_count[date_str] = date_to_count.get(date_str, 0) + 1

    new_name = f"script_{date_str}_{count:03d}.txt"
    new_path = os.path.join(SCRIPTS_DIR, new_name)
    os.rename(fpath, new_path)
    renamed_files.append(new_name)
    existing_ids.add(f"{date_str}_{count:03d}")

# JSONファイルの読み込み
if os.path.exists(STATUS_FILE):
    with open(STATUS_FILE, "r") as f:
        try:
            status_data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ script_status.json が空または壊れています。新しく初期化します。")
            status_data = {}
else:
    status_data = {}

# 👇 ここで空の既存IDを警告
for script_id, info in status_data.items():
    if not info:
        print(f"⚠️ script_id '{script_id}' は存在しますが中身が空です。手動確認してください。")



    
new_ids = []  # ← ここで定義すればOK
completed_ids = {}   # 補完が発生した script_id → 補完されたフィールドのリスト



# 全 script_XXXX_YY.txt に対してステータス追加（既存はスキップ）
for script_file in os.listdir(SCRIPTS_DIR):
    match = re.match(FILENAME_PATTERN, script_file)
    if match:
        script_id = f"{match.group(1)}_{match.group(2)}"
        if (
            script_id not in status_data
            or not isinstance(status_data[script_id], dict)
            or status_data[script_id] is None
        ):
            status_data[script_id] = INITIAL_STATUS.copy()
            new_ids.append(script_id)
        else:
            completed_fields = []
            for key, val in INITIAL_STATUS.items():
                if key not in status_data[script_id]:
                    status_data[script_id][key] = val
                    completed_fields.append(key)
            if completed_fields:
                completed_ids[script_id] = completed_fields

# 保存
with open(STATUS_FILE, "w") as f:
    json.dump(status_data, f, indent=2)

# ログ出力
if new_ids:
    print("✅ 新たに登録された script_id:")
    for sid in new_ids:
        print(f"- {sid}")
else:
    print("✅ 追加された script_id はありません（全て既に存在）")

# ログ出力：補完されたフィールド
if completed_ids:
    print("\n🛠 ステータスを補完した script_id と項目:")
    for sid, fields in completed_ids.items():
        field_list = ", ".join(fields)
        print(f"- {sid}: {field_list}")
