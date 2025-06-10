import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import random

import json
import numpy as np
import re
import math

from moviepy.editor import *
from moviepy.video.fx.all import fadein
from common.constants import SILENCE_DURATION
from pathlib import Path
from dotenv import load_dotenv
from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import get_next_script_id, mark_script_completed
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

# def add_overlay_bars_to_final(video_clip, top_height=100, color=(0, 0, 0)):
#     duration = video_clip.duration

#     top_bar = ColorClip(size=(VIDEO_WIDTH, top_height), color=color, duration=duration)

#     top_bar = top_bar.set_position(("center", 0))

#     return CompositeVideoClip([video_clip, top_bar]).set_audio(video_clip.audio)

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

def make_offset_func(direction, offset, duration):
    if direction == "up":
        return lambda t: 0, lambda t: offset * (1 - 2 * t / duration)
    elif direction == "down":
        return lambda t: 0, lambda t: -offset * (1 - 2 * t / duration)
    elif direction == "left":
        return lambda t: offset * (1 - 2 * t / duration), lambda t: 0
    elif direction == "right":
        return lambda t: -offset * (1 - 2 * t / duration), lambda t: 0
    elif direction == "diag":
        return (
            lambda t: -offset * (1 - 2 * t / duration),
            lambda t: -offset * (1 - 2 * t / duration),
        )
    else:
        return lambda t: 0, lambda t: 0


def make_cropper(x_offset_func, y_offset_func, scale_func=None, duration=1.0):
    def fl(gf, t):
        t = min(t, duration)
        frame = gf(t)
        zoom = scale_func(t) if scale_func else 1.0
        crop_half = int(360 / zoom)

        x_center = 512 + int(x_offset_func(t))
        y_center = 512 + int(y_offset_func(t))

        return frame[
            y_center - crop_half:y_center + crop_half,
            x_center - crop_half:x_center + crop_half
        ]
    return fl



def compose_video(script_id: str):
    timing_path = Path(f"data/stage_2_tag/tags_{script_id}.json")
    subtitle_path = Path(f"data/stage_4_subtitles/subtitles_{script_id}.srt")
    audio_base_dir = Path(f"data/stage_1_audio/{script_id}")
    image_base_dir = Path(f"data/stage_5_image/{script_id}")
    output_dir = Path(f"data/stage_6_output/{script_id}")
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
        video_path_mv = image_base_dir / f"{parent_id}_mv.mp4"
        video_path = image_base_dir / f"{parent_id}.mp4"
        img_path_mv = image_base_dir / f"{parent_id}_mv.png"
        img_path_default = image_base_dir / f"{parent_id}.png"

        # 優先順位: _mv.mp4 → .mp4 → _mv.png → .png
        if video_path_mv.exists():
            asset_path = video_path_mv
            asset_type = "video"
        elif video_path.exists():
            asset_path = video_path
            asset_type = "video"
        elif img_path_mv.exists():
            asset_path = img_path_mv
            asset_type = "image"
        elif img_path_default.exists():
            asset_path = img_path_default
            asset_type = "image"
        else:
            print(f"⚠️ 素材が見つからないためスキップ: {parent_id}")
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

        if asset_type == "image":
            pil_image = Image.open(asset_path).convert("RGB")
            np_frame = np.array(pil_image)
            img_clip = ImageClip(np_frame)

            offset = 50
            x_offset_func = lambda t: 0
            y_offset_func = lambda t: 0
            scale_func = None

            if asset_path.name.endswith("_mv.png"):
                effect = random.choice([
                    "pan_up", "pan_down", "pan_left", "pan_right", "pan_diag",
                    "zoom_in", "zoom_out"
                ])
                print(f"✨ effect applied to {parent_id}: {effect}")

                if effect == "pan_up":
                    x_offset_func, y_offset_func = make_offset_func("up", offset, duration)
                elif effect == "pan_down":
                    x_offset_func, y_offset_func = make_offset_func("down", offset, duration)
                elif effect == "pan_left":
                    x_offset_func, y_offset_func = make_offset_func("left", offset, duration)
                elif effect == "pan_right":
                    x_offset_func, y_offset_func = make_offset_func("right", offset, duration)
                elif effect == "pan_diag":
                    x_offset_func, y_offset_func = make_offset_func("diag", offset, duration)
                elif effect == "zoom_in":
                    scale_func = lambda t: 1.0 + 0.1 * (t / duration)
                elif effect == "zoom_out":
                    scale_func = lambda t: 1.1 - 0.1 * (t / duration)

                img_clip = img_clip.fl(
                    make_cropper(x_offset_func, y_offset_func, scale_func, duration),
                    apply_to=["mask"]
                )

            img_clip = img_clip.set_position(("center", "center")).resize((720, 720))
            clip = img_clip.set_start(start_time).set_duration(duration).set_fps(30)

            print(f"🖼️ 画像clip: parent_id={parent_id}, start={start_time:.2f}s, duration={duration:.2f}s, file={asset_path.name}")

        elif asset_type == "video":
            clip = (
                VideoFileClip(str(asset_path))
                .without_audio()
                .set_start(start_time)
                .set_duration(duration)
                .set_fps(30)
            )

            # ✅ 中央正方形720×720でcropするだけ（パン・ズームなし）
            clip = clip.crop(x_center=clip.w // 2, y_center=clip.h // 2, width=720, height=720)
            clip = clip.set_position(("center", "center"))

        clips.append(clip)  # ← ここ

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

    # ======== 🎵 BGM・効果音の挿入 ========

    project_root = Path(__file__).parent.parent
    fixed_assets_dir = project_root / "fixed_assets"

    bgm_path = fixed_assets_dir / "bgm.mp3"
    se_main_path = fixed_assets_dir / "se_main_title.mp3"
    se_center_path = fixed_assets_dir / "se_title_center.mp3"

    print(f"🔍 BGMパス：{bgm_path}")
    print(f"存在するか？ {bgm_path.exists()}")

    # BGM（全体にループ）
    if not bgm_path.exists():
        print("⚠️ BGMファイルが見つかりません。スキップします。")
        bgm_clip = None
    else:
        bgm_clip = AudioFileClip(str(bgm_path))
        bgm_duration = final_audio.duration
        bgm_loop = afx.audio_loop(bgm_clip, duration=bgm_duration).volumex(0.02)  # 音量調整（0.0〜1.0）

    subtitle_json_path = Path(f"data/stage_4_subtitles/subtitles_{script_id}.json")
    with open(subtitle_json_path, "r", encoding="utf-8") as f:
        subtitle_scenes = json.load(f)


    # 効果音の挿入（main_title: ドドン, title_top: ドン）
    se_clips = []

    for scene in subtitle_scenes:
        scene_type = scene.get("type", "")
        scene_start = scene.get("start_sec", None)
        if scene_start is None:
            continue

        if scene_type == "main_title_top" and se_main_path.exists():
            se_clip = AudioFileClip(str(se_main_path)).set_start(scene_start).volumex(0.5)
            se_clips.append(se_clip)
        elif scene_type == "title_center" and se_center_path.exists():
            se_clip = AudioFileClip(str(se_center_path)).set_start(scene_start).volumex(0.4)
            se_clips.append(se_clip)

    # ======== 🎧 音声合成 ========
    audio_layers = [final_audio]  # ナレーション主体
    if bgm_clip:
        audio_layers.append(bgm_loop)
    audio_layers.extend(se_clips)

    composite_audio = CompositeAudioClip(audio_layers)

    # ✅ base_video をこのタイミングで定義
    base_video = CompositeVideoClip(clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

    # ✅ 音声を合成
    final = base_video.set_audio(composite_audio)

    temp_path = output_dir / "no_subtitles.mp4"
    export_video_high_quality(final, str(temp_path))

        # .ass字幕を使って no_subtitles.mp4 → final.mp4 を生成
    ass_path = Path(f"data/stage_4_subtitles/subtitles_{script_id}.ass")
    final_path = output_dir / "final.mp4"

    if not ass_path.exists():
        raise FileNotFoundError(f"❌ .ass 字幕ファイルが見つかりません: {ass_path}")

    ffmpeg_ass_cmd = (
        f'ffmpeg -y -hwaccel cuda -i "{temp_path}" '
        f'-vf "ass={ass_path.as_posix()}" '
        f'-c:v h264_nvenc -preset slow -b:v 4000k -maxrate 4000k -bufsize 8000k '
        f'-pix_fmt yuv420p -profile:v baseline -level 4.0 '
        f'-c:a aac -b:a 128k -ar 44100 -ac 2 '
        f'"{final_path}"'
    )

    print(f"[ASS字幕焼き込み] {ffmpeg_ass_cmd}")
    ret = os.system(ffmpeg_ass_cmd)
    if ret != 0:
        raise RuntimeError(f"❌ .ass字幕焼き込み処理に失敗しました（code={ret}）")
    print(f"✅ .ass字幕付き動画を保存しました: {final_path}")


    # if subtitle_path.exists():
    #     check_srt_overlaps(subtitle_path)

    #     ffmpeg_command = (
    #         f'ffmpeg -y -hwaccel cuda -i "{temp_path}" '
    #         f'-vf "subtitles=\'{subtitle_path.as_posix()}\':force_style='
    #         f'\'Fontname=Noto Sans CJK JP, Alignment=2,Fontsize=18,Outline=2,MarginV=80,Shadow=1, '
    #         f'PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,ShadowColour=&H80000000,BorderStyle=1, LineSpacing=0\'" '
    #         f'-c:v h264_nvenc -preset slow -b:v 4000k -maxrate 4000k -bufsize 8000k '
    #         f'-pix_fmt yuv420p -profile:v baseline -level 4.0 '
    #         f'-c:a aac -b:a 128k -ar 44100 -ac 2 '
    #         f'"{final_path}"'
    #     )
    #     print(f"[GPU字幕焼き込み] {ffmpeg_command}")
    #     ret = os.system(ffmpeg_command)
    #     if ret != 0:
    #         raise RuntimeError(f"❌ 字幕焼き込みffmpeg処理に失敗しました（code={ret}）")
    #     print(f"✅ 字幕付き動画をGPUで保存しました: {final_path}")

    # else:
    #     print(f"⚠️ 字幕が見つかりません。字幕なしで保存: {temp_path}")
    #     temp_path.rename(final_path)

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
    task_name = "compose"

    while True:
        script_id = get_next_script_id(task_name)
        if not script_id:
            print("✅ 全ての script_id に対して compose が完了しています。")
            break

        print(f"🎬 処理対象のscript_id: {script_id}")
        try:
            compose_video(script_id)
            mark_script_completed(script_id, task_name)
            print(f"✅ 完了: {script_id}")
        except Exception as e:
            print(f"❌ エラー: {script_id} で例外発生: {e}")


