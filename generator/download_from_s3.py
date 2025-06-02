import os
import boto3
from pathlib import Path
from dotenv import load_dotenv


def download_images_from_s3(script_id: str):
    # --- .env.s3 を読み込み ---
    if Path(".env.s3").exists():
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=".env.s3")

    # --- AWSキーを環境変数から取得 ---
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION")

    # --- S3クライアント初期化 ---
    if aws_access_key and aws_secret_key and aws_region:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
    else:
        s3 = boto3.client("s3")  # RunPod向け

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