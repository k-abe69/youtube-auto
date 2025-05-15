import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from pathlib import Path
from datetime import timedelta
from librosa import load, get_duration  # 音声の実長を取得するため

from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import extract_script_id, find_oldest_script_id
from common.constants import SILENCE_DURATION

# スクリプトのバックアップと設定保存（トレーサビリティ確保）
backup_script(__file__)
save_config_snapshot()

# 秒数を SRT の "00:00:00,000" フォーマットに変換
def format_srt_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    milliseconds = int((seconds - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def smart_line_break(text: str, max_len: int = 20):
    # 意味的に自然な改行位置を優先（句読点・助詞など）
    break_chars = ['、', '。', '，', '．', '・', 'が', 'は', 'を', 'に', 'で', 'の', 'と']
    for char in break_chars:
        idx = text.find(char)
        if 0 < idx < max_len:
            return text[:idx+1] + '\n' + text[idx+1:]
    # fallback：半分で切る
    mid = len(text) // 2
    return text[:mid] + '\n' + text[mid:]


# 字幕ファイル（.srt）と構造化JSONを生成
def generate_subtitles(timing_json_path: Path, output_dir: Path, script_id: str):
    # 元となるタイミング情報を読み込み
    with open(timing_json_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)

    srt_lines = []        # SRT出力用の行リスト
    subtitle_json = []    # JSON保存用データ
    current_start = 0.0   # 各sceneの再生開始時間（累積）

    # 字幕の見やすさ調整（遅れて表示、早めに消す）
    DISPLAY_START_DELAY = 0.05
    DISPLAY_EARLY_CUT = 0.05

    # 各sceneごとに処理
    for i, scene in enumerate(timing_data, start=1):
        scene_id = scene["scene_id"]
        text = scene["text"]
        if "\\n" in text:
            text = text.replace("\\n", "\n")
        else:
            text = smart_line_break(text)

        # 音声ファイルから正確なdurationを取得（＋無音0.1sを加算）
        audio_path = Path(f"data/stage_1_audio/{script_id}/{scene_id}.wav")
        if not audio_path.exists():
            print(f"⚠️ 音声ファイルなし: {scene_id}")
            continue

        y, sr = load(audio_path, sr=None)
        duration = get_duration(y=y, sr=sr) + SILENCE_DURATION

        start_sec = current_start
        end_sec = current_start + duration

        # 実際に表示する字幕の時間（やや遅れて出て、早めに消す）
        display_start_sec = start_sec + DISPLAY_START_DELAY
        display_end_sec = max(end_sec - DISPLAY_EARLY_CUT, start_sec + 0.2)

        # SRT形式の字幕を構築
        srt_lines.append(f"{i}")
        srt_lines.append(f"{format_srt_time(display_start_sec)} --> {format_srt_time(display_end_sec)}")
        srt_lines.append(text)
        srt_lines.append("")

        # JSON形式でも字幕情報を保存（正確なstart/endを記録）
        subtitle_json.append({
            "scene_id": scene_id,
            "start_sec": round(start_sec, 2),
            "end_sec": round(end_sec, 2),
            "text": text
        })

        # 次のsceneに備えて再生開始位置を進める
        current_start += duration

    # 出力ディレクトリを作成
    output_dir.mkdir(parents=True, exist_ok=True)

    # SRTファイルとして保存
    srt_path = output_dir / f"subtitles_{script_id}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    # JSON形式でも保存
    json_path = output_dir / f"subtitles_{script_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(subtitle_json, f, ensure_ascii=False, indent=2)

    print(f"✅ 字幕SRT保存: {srt_path}")
    print(f"✅ 字幕JSON保存: {json_path}")

# メイン処理：引数があればそれを使用、なければ最古のscript_idを処理
if __name__ == "__main__":
    input_dir = Path("data/stage_1_audio")
    output_dir = Path("data/stage_4_subtitles")

    if len(sys.argv) > 1:
        script_id = sys.argv[1]
    else:
        script_id = find_oldest_script_id(Path("scripts_done"))

    input_path = input_dir / script_id / f"timing_{script_id}.json"
    if not input_path.exists():
        print(f"❌ 入力ファイルが見つかりません: {input_path}")
        exit()

    generate_subtitles(input_path, output_dir, script_id)
