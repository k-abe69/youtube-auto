import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydub import AudioSegment
import io
import json
import requests
import re
from pathlib import Path
from dotenv import load_dotenv
from common.misread_dict import apply_misread_corrections
from fugashi import Tagger
import shutil
from common.script_utils import parse_args_script_id, mark_script_completed, get_next_script_id, parse_and_generate_voicevox_script

# 環境変数の読み込み
load_dotenv()
VOICEVOX_ENGINE_URL = os.getenv("VOICEVOX_ENGINE_URL", "http://localhost:50021")
SPEAKER_ID = int(os.getenv("VOICEROID_SPEAKER_ID", 66))

# 形態素解析器の初期化
tagger = Tagger()

# テキストをひらがなに変換する関数
def convert_to_hiragana(text: str) -> str:
    return "".join([word.feature.kana if word.feature.kana else word.surface for word in tagger(text)])

# 助詞の発音を修正する関数
def fix_particle_pronunciation(text: str) -> str:
    tokens = tagger(text)
    result = []
    for token in tokens:
        surface = token.surface
        pos = token.feature[0]
        if pos == '助詞':
            if surface == 'は':
                result.append('わ')
                continue
            elif surface == 'へ':
                result.append('え')
                continue
            elif surface == 'を':
                result.append('お')
                continue
        result.append(surface)
    return ''.join(result)

# カナかな変換
def kata_to_hira(text: str) -> str:
    return ''.join(
        chr(ord(char) - 0x60) if 'ァ' <= char <= 'ン' else char
        for char in text
    )


# 音声合成を行う関数
def synthesize_voice(text: str, output_path: Path):
    # 🎯 改行はVOICEVOXに渡すと「えぬ」と読まれるため空白に置換
    text = text.replace("\\n", " ")  # ← バックスラッシュn（2文字）を空白に
    text = text.replace("\n", " ")   # ← 改行文字（1文字）も空白に
    text = apply_misread_corrections(text)
    text = fix_particle_pronunciation(text)
    hiragana_text = convert_to_hiragana(text)
    hiragana_text = kata_to_hira(hiragana_text)  # ← カタカナ→ひらがな
    print(f"[TTS用テキスト]: {hiragana_text}")
    query_payload = {"text": hiragana_text, "speaker": SPEAKER_ID}
    query_res = requests.post(f"{VOICEVOX_ENGINE_URL}/audio_query", params=query_payload)
    if query_res.status_code != 200:
        raise RuntimeError(f"音声クエリ失敗: {query_res.text}")
    query_data = query_res.json()
    # 音声合成パラメータの設定
    query_data["speedScale"] = 1.45
    query_data["intonationScale"] = 1.2
    query_data["pitchScale"] = 0.0
    query_data["volumeScale"] = 1.0
    query_data["prePhonemeLength"] = 0.1
    query_data["postPhonemeLength"] = 0.1
    synthesis_res = requests.post(
        f"{VOICEVOX_ENGINE_URL}/synthesis",
        params={"speaker": SPEAKER_ID},
        data=json.dumps(query_data),
        headers={"Content-Type": "application/json"}
    )
    if synthesis_res.status_code != 200:
        raise RuntimeError(f"音声合成失敗: {synthesis_res.text}")
    with open(output_path, "wb") as f:
        f.write(synthesis_res.content)

# mp3をwavに変換する関数
def convert_to_wav(mp3_path: Path, wav_path: Path):
    sound = AudioSegment.from_file(mp3_path)
    sound += AudioSegment.silent(duration=100)
    sound.export(wav_path, format="wav")

# 台本のテキストからシーンを分割する関数
def split_script_to_scenes(script_text: str) -> list[dict]:
    scenes = []
    lines = script_text.splitlines()
    current_time = None
    current_text = []
    time_pattern = re.compile(r"[（(【\[]\s*(\d+:\d+)\s*[）)】\]]")
    for line in lines:
        match = time_pattern.match(line.strip())
        if match:
            if current_time and current_text:
                scenes.append({
                    "start": current_time,
                    "text": "\n".join(current_text).strip()
                })
            current_time = match.group(1)
            current_text = []
        else:
            current_text.append(line)
    if current_time and current_text:
        scenes.append({
            "start": current_time,
            "text": "\n".join(current_text).strip()
        })
    return scenes

# メイン処理
def main():
    task_name = "audio"
    script_id = parse_args_script_id() or get_next_script_id(task_name)
    if script_id is None:
        return

    input_base_dir = Path("scripts")
    output_base_dir = Path("data_long/stage_1_audio")

    output_base_dir.mkdir(parents=True, exist_ok=True)

    script_txt_path = input_base_dir / f"script_{script_id}.txt"


    output_dir = output_base_dir / script_id
    output_dir.mkdir(parents=True, exist_ok=True)

    tmp_script_path = output_dir / f"script_for_voicevox_{script_id}.txt"
    tmp_meta_path = output_dir / f"script_meta_{script_id}.json"

    # 🎯 ここで (0:00) 付きスクリプトを生成
    parse_and_generate_voicevox_script(script_txt_path, tmp_script_path, tmp_meta_path)

    print(f"🎯 台本読み込み: {tmp_script_path}")
    with open(tmp_script_path, encoding="utf-8") as f:
        script = f.read()

    scenes = split_script_to_scenes(script)

    # 🔽 ここでメタ情報から type を読み込む（id基準）
    with open(tmp_meta_path, encoding="utf-8") as f:
        meta_data = json.load(f)
    scene_id_to_type = {}
    for entry in meta_data:
        if entry["type"] != "source":
            scene_id_to_type[entry["scene_id"]] = entry["type"]


    scene_timings = []
    elapsed = 0.0

    # 各シーンの音声を生成し、タイミング情報を記録
    for i, scene in enumerate(scenes, start=1):
        scene_id = f"scene_{i:02}"
        mp3_path = output_dir / f"{scene_id}.mp3"
        wav_path = output_dir / f"{scene_id}.wav"
        print(f"🗣️ {scene_id} - 音声生成: {scene['text'][:15]}...")

        try:
            synthesize_voice(scene["text"], mp3_path)
            convert_to_wav(mp3_path, wav_path)
            duration = AudioSegment.from_file(mp3_path).duration_seconds
            scene_timings.append({
                "scene_id": scene_id,
                "start_sec": round(elapsed, 2),
                "duration": round(duration, 2),
                "text": scene["text"],
                "type": scene_id_to_type.get(scene_id, "unknown")  # ← これで完全一致

            })
            elapsed += duration
        except Exception as e:
            print(f"❌ エラー ({scene_id}): {e}")

    # タイミング情報を保存
    timing_path = output_dir / f"timing_{script_id}.json"
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(scene_timings, f, ensure_ascii=False, indent=2)
    print(f"✅ タイミング情報保存完了: {timing_path}")

    # 🔽 scene_idに基づいてmetaに時間情報を埋める
    scene_id_to_timing = {
        s["scene_id"]: {
            "start_sec": s["start_sec"],
            "duration": s["duration"]
        }
        for s in scene_timings
    }

    for entry in meta_data:
        timing = scene_id_to_timing.get(entry["scene_id"])
        if timing:
            entry["start_sec"] = timing["start_sec"]
            entry["duration"] = timing["duration"]

    # 🔽 タイミング付きのmetaを再保存（字幕用に使える）
    meta_path_with_timing = output_dir / f"script_meta_{script_id}.json"
    with open(meta_path_with_timing, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=2)
    print(f"✅ メタ情報（タイミング付き）保存完了: {meta_path_with_timing}")
    mark_script_completed(script_id, task_name)
    print(f"✅ ステータス更新完了: {script_id} の {task_name} 完了")

if __name__ == "__main__":
    main()
