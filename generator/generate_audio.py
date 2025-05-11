import sys
import os
# スクリプトの場所からプロジェクトのルートパスをimport対象に追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydub import AudioSegment
import io
import json
import requests
from pydub import AudioSegment
from pathlib import Path
from dotenv import load_dotenv
from common.misread_dict import apply_misread_corrections  # ← 追加


# バックアップと設定のバージョン記録（共通処理）
from common.backup_script import backup_script
backup_script(__file__)
from common.save_config import save_config_snapshot
save_config_snapshot()

# .envから環境変数を読み込み（エンジンURLや話者ID用）
load_dotenv()

VOICEVOX_ENGINE_URL = os.getenv("VOICEVOX_ENGINE_URL", "http://localhost:50021")
SPEAKER_ID = int(os.getenv("VOICEROID_SPEAKER_ID", 1))

# ==== 追加ここから（ルビ変換） ====
# 読み誤りを防ぐため、テキストをひらがなに変換する処理を追加
from fugashi import Tagger

tagger = Tagger()

def convert_to_hiragana(text: str) -> str:
    """MeCabを使ってテキストをひらがなに変換する"""
    return "".join([word.feature.kana if word.feature.kana else word.surface for word in tagger(text)])
# ==== 追加ここまで ====

# 最新の台本（.txt）ファイルを探してパスを返す
def find_latest_script_txt(base_dir="scripts_ok") -> Path:
    txt_files = list(Path(base_dir).rglob("*.txt"))
    if not txt_files:
        raise FileNotFoundError("台本ファイルが見つかりません")
    return max(txt_files, key=lambda p: p.stat().st_mtime)

# 台本テキストを時間付きセリフのシーン単位に分割する
def split_script_to_scenes(script_text: str) -> list[dict]:
    scenes = []
    blocks = script_text.strip().split("（")
    for block in blocks[1:]:
        try:
            time_str, content = block.split("）", 1)
            scenes.append({
                "start": time_str.strip(),  # 台本上の時刻（文字列）
                "text": content.strip()     # セリフ内容
            })
        except ValueError:
            continue
    return scenes

# ==== 追加ここから（助詞の読み方補正） ====
def fix_particle_pronunciation(text: str) -> str:
    """
    ひらがなテキストのうち、助詞で使われる「は」「へ」「を」を
    発音に合わせて「わ」「え」「お」に変換する（表記は変えずに音声用に調整）
    """
    tokens = tagger(text)
    result = []
    for token in tokens:
        surface = token.surface
        pos = token.feature[0]  # ← 主品詞（"助詞" など）

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
# ==== 追加ここまで ====


# VOICEVOXエンジンにテキストを送信して音声（mp3）を生成
def synthesize_voice(text: str, output_path: Path):
    # ==== 修正ここから ====
    # textをひらがなに変換し、助詞の読み間違いも補正する
    text = apply_misread_corrections(text)  # ← 辞書適用を先に
    hiragana_text = convert_to_hiragana(text)
    hiragana_text = fix_particle_pronunciation(hiragana_text)
    query_payload = {"text": hiragana_text, "speaker": SPEAKER_ID}
    # ==== 修正ここまで ====

    # 音声合成のためのクエリ取得
    query_res = requests.post(f"{VOICEVOX_ENGINE_URL}/audio_query", params=query_payload)
    if query_res.status_code != 200:
        raise RuntimeError(f"音声クエリ失敗: {query_res.text}")

    # クエリに音声パラメータを追加（速度・抑揚）
    query_data = query_res.json()
    query_data["speedScale"] = 1.3          # 1.5は速すぎる傾向、1.3くらいが自然かつテンポ良し
    query_data["intonationScale"] = 1.2     # 1.5だと芝居がかりすぎる恐れあり
    query_data["pitchScale"] = 0.0          # 声の高さは自然なままでOK
    query_data["volumeScale"] = 1.0
    query_data["prePhonemeLength"] = 0.1    # 発音前の無音調整で滑らかに
    query_data["postPhonemeLength"] = 0.1   # 発音後の無音調整でブツ切れ対策


    # 合成リクエスト
    synthesis_res = requests.post(
        f"{VOICEVOX_ENGINE_URL}/synthesis",
        params={"speaker": SPEAKER_ID},
        data=json.dumps(query_data),
        headers={"Content-Type": "application/json"}
    )
    if synthesis_res.status_code != 200:
        raise RuntimeError(f"音声合成失敗: {synthesis_res.text}")

    # 出力保存
    with open(output_path, "wb") as f:
        f.write(synthesis_res.content)

# mp3ファイルをwav形式に変換（末尾に無音追加）
def convert_to_wav(mp3_path: Path, wav_path: Path):
    sound = AudioSegment.from_file(mp3_path)
    sound += AudioSegment.silent(duration=100)  # 100msの無音追加
    sound.export(wav_path, format="wav")


def main():
    # 最新の台本ファイルを取得して出力フォルダを作成
    latest_script_path = find_latest_script_txt()
    script_id = latest_script_path.stem.zfill(6)
    output_dir = Path(f"audio/{script_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🎯 台本読み込み: {latest_script_path}")
    with open(latest_script_path, encoding="utf-8") as f:
        script = f.read()

    # 台本をシーンに分割
    scenes = split_script_to_scenes(script)
    scene_timings = []   # タイミング情報（シーンごと）
    elapsed = 0.0        # 各シーンの開始秒数（累積）

    # 各シーンごとに音声生成、wav変換、長さ取得
    for i, scene in enumerate(scenes, start=1):
        scene_id = f"scene_{i:02}"
        mp3_path = output_dir / f"{scene_id}.mp3"
        wav_path = output_dir / f"{scene_id}.wav"
        print(f"🗣️ {scene_id} - 音声生成: {scene['text'][:15]}...")

        try:
            # 音声生成と変換
            synthesize_voice(scene["text"], mp3_path)
            convert_to_wav(mp3_path, wav_path)
            duration = AudioSegment.from_file(mp3_path).duration_seconds

            # 現在のシーンのタイミングを記録
            scene_timings.append({
                "scene_id": scene_id,
                "start_sec": round(elapsed, 2),     # 実際の開始秒（float）
                "duration": round(duration, 2),     # 音声の長さ
                "text": scene["text"]
            })

            elapsed += duration  # 次のシーンの開始秒に加算
        except Exception as e:
            print(f"❌ エラー ({scene_id}): {e}")

    # タイミング情報をJSONに保存（後工程で共通使用）
    timing_path = output_dir / "timing.json"
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(scene_timings, f, ensure_ascii=False, indent=2)
    print(f"✅ タイミング情報保存完了: {timing_path}")

if __name__ == "__main__":
    main()
