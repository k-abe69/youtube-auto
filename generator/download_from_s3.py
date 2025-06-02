import os
import boto3
from pathlib import Path


def download_images_from_s3(script_id: str):

    # --- S3クライアント初期化 ---
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