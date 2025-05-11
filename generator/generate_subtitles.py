import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from pathlib import Path
from datetime import timedelta

from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import resolve_latest_script_info

backup_script(__file__)
save_config_snapshot()

# 秒数を SRT 用の "00:00:00,000" フォーマットに変換
def format_srt_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

# メイン処理
def generate_subtitles(timing_json_path: Path, output_dir: Path):
    with open(timing_json_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)

    srt_lines = []
    subtitle_json = []

    for i, scene in enumerate(timing_data, start=1):
        start_sec = scene["start_sec"]
        duration = scene["duration"]
        end_sec = start_sec + duration
        text = scene["text"]

        srt_lines.append(f"{i}")
        srt_lines.append(f"{format_srt_time(start_sec)} --> {format_srt_time(end_sec)}")
        srt_lines.append(text)
        srt_lines.append("")

        subtitle_json.append({
            "scene_id": scene["scene_id"],
            "start_sec": round(start_sec, 2),
            "end_sec": round(end_sec, 2),
            "text": text
        })

    # 保存処理
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / "subtitles.srt"
    json_path = output_dir / "subtitles.json"

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(subtitle_json, f, ensure_ascii=False, indent=2)

    print(f"✅ 字幕SRT保存: {srt_path}")
    print(f"✅ 字幕JSON保存: {json_path}")

# 実行部
if __name__ == "__main__":
    info = resolve_latest_script_info()
    script_id = info["script_id"]
    timing_json_path = Path(f"audio/{script_id}/timing.json")
    output_dir = Path(f"audio/{script_id}")

    generate_subtitles(timing_json_path, output_dir)
