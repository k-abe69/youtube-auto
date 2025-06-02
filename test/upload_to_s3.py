import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import boto3

# --- 環境変数からキー情報を取得（RunPod Secretsで注入されている前提） ---
aws_access_key = os.environ["AWS_ACCESS_KEY_ID"]
aws_secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]
aws_region = os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-2")
bucket_name = "youtube-auto-bk"

# --- ファイルパスの構成 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
local_file_path = os.path.join(script_dir, "test copy.png")
s3_key = "test/test copy.png"  # S3内でのパス

# --- S3クライアント作成 ---
s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

# --- アップロード実行 ---
try:
    s3.upload_file(local_file_path, bucket_name, s3_key)
    print(f"✅ アップロード成功: s3://{bucket_name}/{s3_key}")
except Exception as e:
    print(f"❌ アップロード失敗: {e}")
