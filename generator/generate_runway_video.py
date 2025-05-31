import os
from runwayml import RunwayML
from dotenv import load_dotenv
import json
from typing import List
import time

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common.script_utils import parse_args_script_id, get_next_script_id, mark_script_completed


load_dotenv()

# 環境変数からAPIキーを取得
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

if not RUNWAY_API_KEY:
    print("エラー: RUNWAY_API_KEY 環境変数が設定されていません")
    exit()

# RunwayMLクライアントを初期化
client = RunwayML(api_key=RUNWAY_API_KEY)

def request_runway(image_url: str):
    image_to_video = client.image_to_video.create(
        model="gen4_turbo",
        prompt_image=image_url,
        ratio="960:960",
        prompt_text="A scenic view of the forest",
        duration=5
    )

    # タスクIDを取得
    task_id = image_to_video.id
    print("生成タスクID:", task_id)


    # 最初のステータス取得まで少し待つ
    print("⏳ 動画生成タスクの初期化を待機中...")
    time.sleep(10)  # 最初のポーリングまで10秒待機


    # タスクの状態を取得
    task = client.tasks.retrieve(task_id)

    # タスクの完了をポーリングで待機
    while task.status not in ['SUCCEEDED', 'FAILED']:
        print(f"⌛ 現在のステータス: {task.status} ... 次の確認まで10秒待機")
        time.sleep(10)
        task = client.tasks.retrieve(task_id)

    if task.status == 'SUCCEEDED':
        print("✅ 動画生成完了！動画URL:")

        output = task.output

        if isinstance(output, list) and len(output) > 0 and isinstance(output[0], str):
            print(output[0])
        else:
            print("⚠ 想定外の出力形式でした。内容:", output)

    else:
        print("❌ 動画生成に失敗しました。")



# これは仮の構造。実際には Google Drive API を使って画像URLを取得する処理に置き換える
def get_image_urls_for_script(script_id: str) -> List[str]:
    # Google Drive上の特定フォルダから画像URLを取得する想定
    # ここではダミーのURLを順に返す
    base_url = f"https://drive.google.com/uc?id={{image_id}}"
    dummy_image_ids = ["img001", "img002", "img003"]
    return [base_url.format(image_id=img_id) for img_id in dummy_image_ids]


# メイン処理

# 引数として script_id を受け取る
task_name = "video"
script_id = parse_args_script_id() or get_next_script_id(task_name)
if script_id is None:
    exit()

print(f"🎬 処理対象のscript_id: {script_id}")
image_urls = get_image_urls_for_script(script_id)

for url in image_urls:
    print(f"🖼️ 使用画像: {url}")
    request_runway(url)

# 全画像処理後に完了マーク
mark_script_completed(script_id)
print(f"✅ script_id {script_id} を完了としてマークしました")