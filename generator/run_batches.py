import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess
import time
from pathlib import Path
from common.script_utils import parse_args_script_id, get_next_script_id, mark_script_completed

# 未処理の台本IDを取得
task_name = "image"
script_id = parse_args_script_id()

def run_batches_for(script_id):
    json_path = Path(f"data/stage_3_prompt/prompts_{script_id}.json")
    if not json_path.exists():
        print(f"❌ JSONファイルが見つかりません: {json_path}")
        return

    start_index = 1
    batch_size = 5

    while True:
        print(f"\n🌀 バッチ実行: script_id={script_id}, index {start_index} 〜 {start_index + batch_size - 1}")
        try:
            result = subprocess.run(
                ["python", "generator/fetch_images.py",
                 "--script_id", script_id,
                 "--start_index", str(start_index),
                 "--batch_size", str(batch_size)],
                check=False
            )

            if result.returncode == 1:
                print(f"✅ {script_id} の全バッチ処理が完了しました。")
                mark_script_completed(script_id, task_name)
                break
            elif result.returncode != 0:
                print(f"❌ {script_id} の処理で異常終了（コード {result.returncode}）しました。")
                break

            start_index += batch_size
            print("💤 2秒休憩中...\n")
            time.sleep(2)

        except KeyboardInterrupt:
            print("⛔️ 処理が中断されました。")
            break
        except Exception as e:
            print(f"❌ バッチ実行中にエラーが発生しました: {type(e).__name__}: {e}")
            break

if script_id:
    run_batches_for(script_id)
else:
    while True:
        script_id = get_next_script_id(task_name)
        if not script_id:
            print("✅ 全ての台本に対して image タスクが完了しています。")
            break
        run_batches_for(script_id)