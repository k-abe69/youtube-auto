from moviepy.editor import VideoClip

def export_video_high_quality(clip: VideoClip, output_path: str):
    """
    高画質・高再現性・高互換性で動画を書き出す共通関数。
    ffmpegのビットレート・プロファイル・ピクセル形式・音声設定などをすべて明示。

    Parameters:
        clip (VideoClip): 書き出すmoviepyクリップ
        output_path (str): 出力先パス（例："output/final.mp4"）
    """
    clip.write_videofile(
        output_path,
        codec="libx264",               # 映像：H.264固定
        audio_codec="aac",             # 音声：AAC（汎用）
        fps=30,                        # フレームレート統一
        preset="medium",               # エンコード速度と画質のバランス
        ffmpeg_params=[
            "-b:v", "4000k",
            "-maxrate", "4000k",
            "-bufsize", "8000k",
            "-pix_fmt", "yuv420p",
            "-profile:v", "baseline",
            "-level", "4.0",
            "-ac", "2",
            "-ar", "44100",
            "-b:a", "128k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1"
        ]
    )
