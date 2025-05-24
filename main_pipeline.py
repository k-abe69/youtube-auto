import subprocess
import sys
import os
from common.script_utils import resolve_latest_script_info
from common.backup_script import backup_script
from common.save_config import save_config_snapshot

backup_script(__file__)
save_config_snapshot()

def run_step(command: list[str], description: str):
    print(f"\n=== {description} ===")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ エラー: {description} で失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    info = resolve_latest_script_info()
    script_id = info["script_id"]
    print(f"[対象台本] script_id: {script_id}")

    run_step(["python", "generator/generate_audio.py"], "音声生成")
    run_step(["python", "generator/tag_generator.py"], "タグ生成")
    run_step(["python", "generator/fetch_images.py"], "画像取得")
    run_step(["python", "generator/generate_subtitles.py"], "字幕生成")
    run_step(["python", "generator/compose_video.py"], "動画合成")

    run_step(["python", "generator/generate_thumbnail.py", script_id], "サムネイル生成")
    run_step(["python", "generator/generate_ed.py", script_id], "ED生成")
    run_step(["python", "generator/merge_final_video.py", script_id], "最終結合")

    print("\n✅ パイプライン処理が完了しました！ output/{}/final_compatible.mp4 を確認してください".format(script_id))
