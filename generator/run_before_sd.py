import subprocess
import os
import json
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.script_utils import get_next_script_id

# ステータスファイルを整備してから処理を開始
subprocess.run(["python", "common/generate_status.py"])

# タスクは audio が最初のステージ
while True:
    script_id = get_next_script_id("audio")  # audioを起点に
    if not script_id:
        print("全ての台本に対する処理が完了、または依存未完了です。終了します。")
        break

    print(f"▶️ 処理対象 script_id: {script_id}")

    # 各ステージを順番に実行
    subprocess.run(["python", "generator/generate_audio.py", "--script_id", script_id])
    subprocess.run(["python", "generator/tag_generator.py", "--script_id", script_id])
    subprocess.run(["python", "generator/generate_sd_prompt.py", "--script_id", script_id])
    subprocess.run(["python", "generator/generate_subtitles.py", "--script_id", script_id])


    print(f"[✓] script_id={script_id} に対する全処理が完了しました。\n")
