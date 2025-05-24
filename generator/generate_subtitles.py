import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from pathlib import Path
from datetime import timedelta
from librosa import load, get_duration  # 音声の実長を取得するため

from common.backup_script import backup_script
from common.save_config import save_config_snapshot
from common.script_utils import extract_script_id, find_oldest_script_id, resolve_script_id 
from common.constants import SILENCE_DURATION

# スクリプトのバックアップと設定保存（トレーサビリティ確保）
backup_script(__file__)
save_config_snapshot()

# ハイライト単語辞書を読み込み
highlight_path = Path("fixed_assets/subtitle_highlight_words.json")
if highlight_path.exists():
    with open(highlight_path, "r", encoding="utf-8") as f:
        highlight_dict = json.load(f)
else:
    highlight_dict = {"emotional": [], "emphasis": []}

def apply_highlight_tags(text: str, highlight_dict: dict) -> str:
    for word in highlight_dict.get("emotional", []):
        text = text.replace(word, r"{\1c&H33FFFF&}" + word + r"{\r}")  # yellow
    for word in highlight_dict.get("emphasis", []):
        text = text.replace(word, r"{\1c&H0000FF&}" + word + r"{\r}")  # blue（赤なら &H0000FF& を赤コードに変更）
    return text




# 秒数を SRT の "00:00:00,000" フォーマットに変換
def format_srt_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    milliseconds = int((seconds - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h:01}:{m:02}:{s:02}.{cs:02}"


def smart_line_break(text: str, max_len: int = 20):
    # 意味的に自然な改行位置を優先（句読点・助詞など）
    break_chars = ['、', '。', '，', '．', '・', 'が', 'は', 'を', 'に', 'で', 'の', 'と']
    for char in break_chars:
        idx = text.find(char)
        if 0 < idx < max_len:
            return text[:idx+1] + r'\N' + text[idx+1:]
    # fallback：半分で切る
    mid = len(text) // 2
    return text[:mid] + r'\N' + text[mid:]


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
        # すべての改行をASS用改行に統一
        text = scene["text"].replace("\\n", "\n").replace("\n", r"\N")
        if r"\N" not in text:
            text = smart_line_break(text)


        # 音声ファイルから正確なdurationを取得（＋無音0.1sを加算）
        audio_path = Path(f"data/stage_1_audio/{script_id}/{scene_id}.wav")
        if not audio_path.exists():
            if scene["type"] == "source":
                # 音声はないが timing 情報は使いたい
                duration = scene["duration"]
            else:
                print(f"⚠️ 音声ファイルなし: {scene_id}")
                continue
        else:
            y, sr = load(audio_path, sr=None)
            duration = get_duration(y=y, sr=sr) + SILENCE_DURATION
        
        if scene["type"] == "title":
            scene_id = scene["scene_id"]
            text = scene["text"]
            start_sec = current_start
            end_sec = current_start + duration

            # ① 中央表示（メタdurationでぴったり表示）
            subtitle_json.append({
                "scene_id": scene_id + "_center",
                "start_sec": round(start_sec, 2),
                "end_sec": round(end_sec, 2),
                "text": text,
                "type": "title_center"
            })

            # ② 次のtitleを探す
            next_title_start = None
            for future_scene in timing_data[i:]:
                if future_scene["type"] == "title":
                    next_title_start = future_scene["start_sec"]
                    break

            # fallback: 最後のsceneの end_sec を代入（常にtitle_topを出力）
            if next_title_start is None:
                last_scene = timing_data[-1]
                next_title_start = last_scene["start_sec"] + last_scene["duration"]

            # 上部表示：startは titleのendから、endは次のtitleのstart
            subtitle_json.append({
                "scene_id": scene_id + "_top",
                "start_sec": round(end_sec, 2),
                "end_sec": round(next_title_start, 2),
                "text": text,
                "type": "title_top"
            })

            current_start += duration
            continue


        if scene["type"] == "source":
            start_sec = current_start - duration
            end_sec = current_start
            # current_start は更新しない
        else:
            start_sec = current_start
            end_sec = current_start + duration
            current_start = end_sec


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
            "text": text,
            "type": scene["type"]
        })


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

def generate_ass_from_json(json_path: Path, output_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    # 次のtitleまでの時間探索（title保持のため）
    title_timing = [s for s in scenes if s["type"] == "title_center"]
    title_timing.append({"start_sec": 99999})  # ダミー

    ass_events = []
    for i, scene in enumerate(scenes):
        if scene["type"] == "title_top":
            continue  # TitleTop をスキップ
        style = {
            "main_title": "MainTitle",
            "title_center": "TitleCenter",
            "title_top": "TitleTop",
            "source": "Source",
            "summary": "Summary"
        }.get(scene["type"], "Summary")
        # sourceだけレイヤーを1に（最前面）
        layer = 1 if scene["type"] == "source" else 0


        start = scene["start_sec"]

        if scene["type"] == "title_top":
            for t in title_timing:
                if t["start_sec"] > start:
                    end = t["start_sec"]
                    break
        else:
            end = scene["end_sec"]




        text = scene["text"].replace("\\n", "\n").replace("\n", r"\N").replace(',', '，')
        text = apply_highlight_tags(text, highlight_dict)

        ass_events.append(
            f"Dialogue: {layer},{format_ass_time(start)},{format_ass_time(end)},{style},,"
            f"0,0,0,,{text}"
        )


    ass_header = """[Script Info]
Title: Generated
ScriptType: v4.00+
Collisions: Normal
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MainTitle,Noto Sans CJK JP,26,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,13,1,5,10,10,30,1

Style: TitleCenter,Noto Sans CJK JP,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,8,0,5,10,10,30,1
Style: TitleTop,Noto Sans CJK JP,0,&H00CCCCCC,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,8,0,8,10,10,30,1

Style: Source,Noto Sans CJK JP,10,&H00CCCCCC,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,5,0,2,0,0,80,1

Style: Summary,Noto Sans CJK JP,18,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,5,0,2,0,0,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,
#         Bold, Italic, Underline, StrikeOut,
#         ScaleX, ScaleY, Spacing, Angle,
#         BorderStyle, Outline, Shadow,
#         Alignment, MarginL, MarginR, MarginV,
#         Encoding

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_header)
        f.write("\n".join(ass_events))

    print(f"✅ ASS字幕保存: {output_path}")


# メイン処理：引数があればそれを使用、なければ最古のscript_idを処理
if __name__ == "__main__":
    input_dir = Path("data/stage_1_audio")
    output_dir = Path("data/stage_4_subtitles")

    script_id = resolve_script_id()

    input_path = input_dir / script_id / f"script_meta_{script_id}.json"
    if not input_path.exists():
        print(f"❌ 入力ファイルが見つかりません: {input_path}")
        exit()

    generate_subtitles(input_path, output_dir, script_id)

    # JSONファイルの出力先を明示的に定義
    json_path = output_dir / f"subtitles_{script_id}.json"

    generate_ass_from_json(
        json_path=json_path,  # 生成済みsubtitle_jsonへのパス
        output_path=output_dir / f"subtitles_{script_id}.ass"
    )
