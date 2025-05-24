import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess
import time
from pathlib import Path
from common.script_utils import resolve_script_id

# 台本IDを取得
script_id = resolve_script_id()

# 処理対象のJSONファイルが存在するかチェック
json_path = Path(f"data/stage_3_prompt/prompts_{script_id}.json")
if not json_path.exists():
    print(f"❌ JSONファイルが見つかりません: {json_path}")
    exit(1)

# バッチ処理の設定
start_index = 1
batch_size = 5  # 必要に応じて調整可能

while True:
    print(f"\n🌀 バッチ実行: index {start_index} 〜 {start_index + batch_size - 1}")
    try:
        result = subprocess.run(
            ["python", "generator_old/fetch_images.py", script_id, str(start_index), str(batch_size)],
            check=False
        )

        # fetch_images.py の戻り値で判断（0: 続きあり、1: 完了）
        if result.returncode == 1:
            print("✅ 全バッチ処理が完了しました。")
            break

        start_index += batch_size
        print("💤 2秒休憩中...\n")
        time.sleep(2)  # 小休止（GPUリセットや温度低下のため）

    except KeyboardInterrupt:
        print("⛔️ 処理が中断されました。")
        break
    except Exception as e:
        print(f"❌ バッチ実行中にエラーが発生しました: {type(e).__name__}: {e}")
        break
