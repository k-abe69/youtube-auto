from moviepy.editor import VideoFileClip, concatenate_videoclips
from pathlib import Path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common.script_utils import extract_script_id, find_oldest_script_id, resolve_script_id 


def merge_final_video(script_id: str):
    print(f"\n🎬 最終結合処理 開始：{script_id}")

    # 各入力ファイルのパス（命名規則に準拠）
    thumb_path = Path(f"data/thumbnails/{script_id}_thumb.mp4")
    core_path = Path(f"data/stage_5_output/{script_id}/final.mp4")  # 字幕焼き込み済
    ed_path = Path(f"data/ed/{script_id}_ed_video.mp4")

    # 出力先
    output_dir = Path("data/final")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{script_id}_final_merged.mp4"

    # 存在チェック
    for path in [thumb_path, core_path, ed_path]:
        if not path.exists():
            raise FileNotFoundError(f"❌ ファイルが見つかりません: {path}")

    # 読み込みと結合
    thumb_clip = VideoFileClip(str(thumb_path)).resize((720, 1280))
    core_clip  = VideoFileClip(str(core_path)).resize((720, 1280))
    ed_clip    = VideoFileClip(str(ed_path)).resize((720, 1280))


    final_clip = concatenate_videoclips([thumb_clip, core_clip, ed_clip], method="compose")

    # 高品質で書き出し
    from common.video_export import export_video_high_quality
    export_video_high_quality(final_clip, str(output_path))
    print(f"✅ 最終動画書き出し完了: {output_path}")

if __name__ == "__main__":
    script_id = resolve_script_id()

    if len(sys.argv) < 2:
        print("使い方: python merge_final_video.py <script_id>")
        sys.exit(1)
    merge_final_video(sys.argv[1])
