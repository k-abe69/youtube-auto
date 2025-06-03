import os
import boto3
from pathlib import Path

from dotenv import load_dotenv

# .env.s3 ファイルの読み込み
dotenv_path = Path(__file__).parent.parent / ".env.s3"
load_dotenv(dotenv_path)

# 環境変数からキー情報を取得
aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
aws_region = os.environ.get("AWS_DEFAULT_REGION")  # デフォルトは東京リージョン


def download_images_from_s3(script_id: str):

    # --- S3クライアント初期化 ---
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )
    bucket_name = "youtube-auto-bk"
    s3_prefix = f"stage_5_image/sd_images/{script_id}/"
    local_dir = Path(f"data/stage_5_image/{script_id}")
    local_dir.mkdir(parents=True, exist_ok=True)

    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_prefix)

    if "Contents" not in response:
        print("⚠️ S3に対象ファイルが見つかりませんでした。")
        return

    for obj in response["Contents"]:
        s3_key = obj["Key"]
        if not s3_key.endswith(".png"):
            continue

        filename = s3_key.split("/")[-1]
        local_path = local_dir / filename

        try:
            s3.download_file(bucket_name, s3_key, str(local_path))
            print(f"✅ ダウンロード成功: {filename}")
        except Exception as e:
            print(f"❌ ダウンロード失敗: {filename} → {e}")

if __name__ == "__main__":
    # テスト用script_idを指定
    download_images_from_s3("20250603_005")
