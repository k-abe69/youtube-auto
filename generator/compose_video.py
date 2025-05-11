import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from pathlib import Path
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import resolve_latest_script_info

backup_script(__file__)
save_config_snapshot()

# 動画の幅と高さ（縦動画向け）
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280

# 字幕付きの動画を出力
def compose_video(script_id: str, date_path: str):
    timing_path = Path(f"audio/{script_id}/timing.json")
    audio_base_dir = Path(f"audio/{script_id}")
    image_base_dir = Path(f"images/{script_id}")
    output_dir = Path(f"output/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(timing_path, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    clips = []

    for scene in scenes:
        scene_id = scene["scene_id"]
        start = scene["start_sec"]
        duration = scene["duration"]
        img_path = image_base_dir / f"{scene_id}.jpg"
        audio_path = audio_base_dir / f"{scene_id}.wav"

        if not img_path.exists() or not audio_path.exists():
            print(f"⚠️ スキップ: {scene_id}（画像または音声が見つからない）")
            continue

        img_clip = (
            ImageClip(str(img_path))
            .set_duration(duration)
            .resize(height=VIDEO_HEIGHT)  # 高さ優先リサイズ
            .set_position("center")
        )
        audio_clip = AudioFileClip(str(audio_path)).subclip(0, duration)
        img_clip = img_clip.set_audio(audio_clip)
        clips.append(img_clip)

    if not clips:
        print("❌ 有効なシーンがありません。動画を生成できません。")
        return

    final = concatenate_videoclips(clips, method="compose")
    temp_path = output_dir / "no_subtitles.mp4"
    final.write_videofile(str(temp_path), fps=30)

    # 字幕を重ねて最終出力
    subtitle_path = Path(f"audio/{script_id}/subtitles.srt")
    final_path = output_dir / "final.mp4"

    if subtitle_path.exists():
        ffmpeg_command = f'ffmpeg -y -i "{temp_path}" -vf subtitles="{subtitle_path.as_posix()}" -c:a copy "{final_path}"'
        print(f"[ffmpeg実行] {ffmpeg_command}")
        os.system(ffmpeg_command)
        print(f"✅ 字幕付き動画を保存しました: {final_path}")
    else:
        print(f"⚠️ 字幕が見つかりません。字幕なしで保存: {temp_path}")
        temp_path.rename(final_path)


    # ✅ 再生互換版の出力（解像度を偶数に丸めて再エンコード）
    compatible_path = output_dir / "final_compatible.mp4"
    ffmpeg_compat_cmd = (
        f'ffmpeg -y -i "{final_path}" '
        f'-vf "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p" '
        f'-profile:v baseline -level 3.0 -c:v libx264 -c:a copy "{compatible_path}"'
    )
    print(f"[ffmpeg互換変換] {ffmpeg_compat_cmd}")
    os.system(ffmpeg_compat_cmd)
    print(f"✅ 再生互換版動画を保存しました: {compatible_path}")

if __name__ == "__main__":
    info = resolve_latest_script_info()
    compose_video(info["script_id"], info["date_path"])
