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
aws_region = os.environ.get("AWS_DEFAULT_REGION")

def upload_images_to_s3(script_id: str):
    # S3クライアント初期化
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )

    bucket_name = "youtube-auto-bk"
    local_dir = Path(f"data_long/stage_5_image/{script_id}/images")
    s3_prefix = f"stage_5_image/sd_images/{script_id}/"

    if not local_dir.exists():
        print("⚠️ ローカル画像ディレクトリが存在しません。")
        return

    for image_path in local_dir.glob("*.png"):
        s3_key = f"{s3_prefix}{image_path.name}"
        try:
            s3.upload_file(str(image_path), bucket_name, s3_key)
            print(f"✅ アップロード成功: {image_path.name}")
        except Exception as e:
            print(f"❌ アップロード失敗: {image_path.name} → {e}")

if __name__ == "__main__":
    # テスト用script_idを指定
    upload_images_to_s3("20250611_001")
    upload_images_to_s3("20250611_002")
    upload_images_to_s3("20250611_003")
    upload_images_to_s3("20250611_004")
