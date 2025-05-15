import subprocess
from common.script_utils import find_oldest_script_id
from pathlib import Path

def run_step(script, script_id):
    cmd = ["python", f"generator/{script}.py", script_id]
    print(f"▶️ 実行中: {script}.py ({script_id})")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"❌ エラー: {script}.py ({script_id})")
        exit(1)

def check_existing_outputs(script_id):
    stage_paths = [
        Path(f"data/stage_1_audio/{script_id}/timing_{script_id}.json"),
        Path(f"data/stage_2_tag/tags_{script_id}.json"),
        Path(f"data/stage_3_images/{script_id}/scene_01.jpg"),
        Path(f"data/stage_4_subtitles/subtitles_{script_id}.srt"),
        Path(f"scripts_done/script_{script_id}.txt"),
    ]
    for path in stage_paths:
        if path.exists():
            print(f"🛑 既存データあり: {path}")
            print("⚠️ 処理を中止します。script_id を変えるか、対象ファイルを削除してください。")
            exit(1)

def main():
    # ✅ 台本IDの取得（scripts_ok から最も若いID）
    script_id = find_oldest_script_id(Path("scripts_ok"))
    print(f"📘 対象台本: {script_id}")
    check_existing_outputs(script_id)  # ← ここで事前チェック

    # ステージ順に実行
    run_step("generate_audio", script_id)
    run_step("tag_generator", script_id)
    run_step("generate_subtitles", script_id)
    run_step("fetch_images", script_id)
    run_step("compose_video", script_id)

    print(f"✅ 完了: script_id = {script_id}")

if __name__ == "__main__":
    main()
