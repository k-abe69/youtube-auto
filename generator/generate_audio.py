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
from common.script_utils import extract_script_id, find_oldest_script_file  # ← 修正ポイント

# 環境変数の読み込み
load_dotenv()
VOICEVOX_ENGINE_URL = os.getenv("VOICEVOX_ENGINE_URL", "http://localhost:50021")
SPEAKER_ID = int(os.getenv("VOICEROID_SPEAKER_ID", 1))

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
    input_base_dir = Path("scripts_ok")
    done_base_dir = Path("scripts_done")
    output_base_dir = Path("data/stage_1_audio")

    done_base_dir.mkdir(exist_ok=True)
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # 台本ファイル単位で最も若いものを取得
    script_txt = find_oldest_script_file(input_base_dir)
    if not script_txt:
        print("未処理の台本が見つかりません。")
        return

    script_id = extract_script_id(script_txt.name)
    script_dir = script_txt.parent
    output_dir = output_base_dir / script_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🎯 台本読み込み: {script_txt}")
    with open(script_txt, encoding="utf-8") as f:
        script = f.read()

    scenes = split_script_to_scenes(script)
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
                "text": scene["text"]
            })
            elapsed += duration
        except Exception as e:
            print(f"❌ エラー ({scene_id}): {e}")

    # タイミング情報を保存
    timing_path = output_dir / f"timing_{script_id}.json"
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(scene_timings, f, ensure_ascii=False, indent=2)
    print(f"✅ タイミング情報保存完了: {timing_path}")

    # 台本ファイルを処理済みへ移動
    shutil.move(str(script_txt), done_base_dir / script_txt.name)
    print(f"📁 処理済み台本を移動: {done_base_dir / script_txt.name}")

if __name__ == "__main__":
    main()
