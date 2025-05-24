import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import numpy as np
import re

from moviepy.editor import *
from moviepy.video.fx.all import fadein
from common.constants import SILENCE_DURATION
from pathlib import Path
from dotenv import load_dotenv
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import find_oldest_script_id, resolve_script_id 
from PIL import Image
from common.video_export import export_video_high_quality

from datetime import datetime, timedelta
from collections import defaultdict


# 初期処理
backup_script(__file__)
save_config_snapshot()
load_dotenv()

# 定数
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280




def parse_srt_time(t: str) -> float:
    dt = datetime.strptime(t.strip(), "%H:%M:%S,%f")
    return timedelta(
        hours=dt.hour,
        minutes=dt.minute,
        seconds=dt.second,
        microseconds=dt.microsecond
    ).total_seconds()

def check_srt_overlaps(srt_path: Path):
    print("\n🧐 字幕オーバーラップチェック開始")
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = re.findall(r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n", content)

    prev_end = 0
    for idx, (_, start_str, end_str) in enumerate(entries):
        start_sec = parse_srt_time(start_str)
        end_sec = parse_srt_time(end_str)

        if start_sec < prev_end:
            print(f"⚠️ 重複: #{idx+1} start={start_sec:.3f}s overlaps with previous end={prev_end:.3f}s")
        prev_end = end_sec

    print("✅ 字幕オーバーラップチェック完了\n")

def compose_video(script_id: str):
    timing_path = Path(f"data/stage_2_tag/tags_{script_id}.json")
    subtitle_path = Path(f"data/stage_4_subtitles/subtitles_{script_id}.srt")
    audio_base_dir = Path(f"data/stage_1_audio/{script_id}")
    image_base_dir = Path(f"data/stage_3_images/{script_id}")
    output_dir = Path(f"data/stage_5_output/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(timing_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        scenes = data["scenes"]

    clips = []
    audio_clips = []
    current_start = 0.0  # 累積型の再生開始時刻（すべての基準）

    # ✅ parent_scene_id ごとに背景画像を表示
    from collections import defaultdict

    # ✅ parent_scene_id ごとに背景画像を表示（音声と完全同期させる）
    parent_scene_map = defaultdict(list)
    for scene in scenes:
        parent_scene_map[scene["parent_scene_id"]].append(scene)

    timeline_pointer = 0.0  # 画像表示の累積開始時間。音声と同じく前から順に積み上げていく

    for parent_id, group in parent_scene_map.items():
        img_path = image_base_dir / f"{parent_id}.jpg"

        if not img_path.exists():
            print(f"⚠️ スキップ: parent_scene_id={parent_id}（画像が見つからない）")
            continue

        # ✅ そのグループに含まれる各 scene_id.wav の再生時間（＋SILENCE）を積算
        group_duration = 0.0
        for scene in group:
            audio_path = audio_base_dir / f"{scene['scene_id']}.wav"
            if not audio_path.exists():
                continue
            audio_clip = AudioFileClip(str(audio_path))
            group_duration += audio_clip.duration + SILENCE_DURATION

        # ✅ この親sceneの画像を表示する開始時刻と表示時間を決定（＝音声と完全一致）
        start_time = timeline_pointer
        duration = group_duration
        end_time = start_time + duration
        timeline_pointer = end_time  # 次の親sceneの画像表示開始時間に更新

        # ✅ 背景画像を設定（全画面、センター、durationぶん表示）
        image_clip = (
            ImageClip(str(img_path))
            .resize((VIDEO_WIDTH, VIDEO_HEIGHT))
            .set_position("center")
            .set_duration(duration)
            .set_start(start_time)
        )

        # ✅ 冒頭シーンだけフェードイン演出を適用
        if parent_id == "000":
            image_clip = image_clip.fx(fadein, 0.3)

        if clips:
            # 前の clip の end_time を取得
            prev_clip = clips[-1]
            crossfade_duration = 0.1  # 秒数（自然なフェード推奨）

            # 前のclipにクロスフェード適用
            prev_clip = prev_clip.crossfadeout(crossfade_duration)
            image_clip = image_clip.crossfadein(crossfade_duration)

            # 差し替え
            clips[-1] = prev_clip

        clips.append(image_clip)


    for i, scene in enumerate(scenes):
        scene_id = scene["scene_id"]
        audio_path = audio_base_dir / f"{scene_id}.wav"

        if not audio_path.exists():
            print(f"⚠️ スキップ: {scene_id}（画像または音声が見つからない）")
            continue

        # 音声読み込み + 無音0秒追加
        audio_clip = AudioFileClip(str(audio_path))
        silence = AudioClip(make_frame=lambda t: [0], duration=SILENCE_DURATION, fps=44100).set_fps(44100)
        audio_clip = concatenate_audioclips([audio_clip, silence])
        real_duration = audio_clip.duration  # SILENCE_DURATIONを含む

        # 安全な時間定義
        start_time = current_start
        end_time = start_time + real_duration
        duration = end_time - start_time  # ← duration を先に定義！


        # 音声clip（明示的にstart/endを指定）
        audio_clip = audio_clip.set_start(start_time).set_end(end_time)
        audio_clips.append(audio_clip)

        current_start = end_time  # 次のsceneの基準時間に進める

    if not clips:
        print("❌ 有効なsceneがありません。動画を生成できません。")
        return

    final_audio = concatenate_audioclips(audio_clips)

    # チラつき対策
    final = CompositeVideoClip(clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT)).set_audio(final_audio)

    temp_path = output_dir / "no_subtitles.mp4"
    export_video_high_quality(final, str(temp_path))

    final_path = output_dir / "final.mp4"

    if subtitle_path.exists():
        check_srt_overlaps(subtitle_path)

        ffmpeg_command = (
            f'ffmpeg -y -hwaccel cuda -i "{temp_path}" '
            f'-vf "subtitles=\'{subtitle_path.as_posix()}\':force_style='
            f'\'Fontname=Noto Sans CJK JP, Alignment=2,Fontsize=18,Outline=2,MarginV=80,Shadow=1, '
            f'PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,ShadowColour=&H80000000,BorderStyle=1, LineSpacing=0\'" '
            f'-c:v h264_nvenc -preset slow -b:v 4000k -maxrate 4000k -bufsize 8000k '
            f'-pix_fmt yuv420p -profile:v baseline -level 4.0 '
            f'-c:a aac -b:a 128k -ar 44100 -ac 2 '
            f'"{final_path}"'
        )
        print(f"[GPU字幕焼き込み] {ffmpeg_command}")
        ret = os.system(ffmpeg_command)
        if ret != 0:
            raise RuntimeError(f"❌ 字幕焼き込みffmpeg処理に失敗しました（code={ret}）")
        print(f"✅ 字幕付き動画をGPUで保存しました: {final_path}")

    else:
        print(f"⚠️ 字幕が見つかりません。字幕なしで保存: {temp_path}")
        temp_path.rename(final_path)

    compatible_path = output_dir / "final_compatible.mp4"
    ffmpeg_compat_cmd = (
        f'ffmpeg -y -hwaccel cuda -i "{final_path}" '
        f'-vf "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p" '
        f'-c:v h264_nvenc -preset slow -b:v 4000k -maxrate 4000k -bufsize 8000k -pix_fmt yuv420p '
        f'-profile:v baseline -level 4.0 '
        f'-c:a aac -b:a 128k -ar 44100 -ac 2 '
        f'"{compatible_path}"'
    )


    print(f"[GPU互換変換] {ffmpeg_compat_cmd}")
    os.system(ffmpeg_compat_cmd)
    print(f"✅ 再生互換版動画（GPU使用）を保存しました: {compatible_path}")


if __name__ == "__main__":
    script_id = resolve_script_id()
    compose_video(script_id)
