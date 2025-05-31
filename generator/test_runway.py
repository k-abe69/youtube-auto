import os
from runwayml import RunwayML
from dotenv import load_dotenv


load_dotenv()

# 環境変数からAPIキーを取得
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

if not RUNWAY_API_KEY:
    print("エラー: RUNWAY_API_KEY 環境変数が設定されていません")
    exit()

# RunwayMLクライアントを初期化
client = RunwayML(api_key=RUNWAY_API_KEY)

# 動画生成リクエスト
image_to_video = client.image_to_video.create(
    model="gen4_turbo",
    prompt_image="https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_1280.jpg",
    ratio="960:960",
    prompt_text="A scenic view of the forest",
    duration=5
)

import time

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
