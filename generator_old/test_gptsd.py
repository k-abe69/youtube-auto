from openai import OpenAI

import requests
import base64
from PIL import Image
from io import BytesIO
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv

# OpenAI APIキー読み込み
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# 2. GPTに画像用プロンプト生成依頼

# GPTでプロンプト生成
chat_response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a professional image prompt engineer for Stable Diffusion."},
        {"role": "user", "content": "構図: やや斜め右上から街中想定で撮る。顔: 日本人とロシア人のハーフで白髪美人。行動: 札束を持って笑顔で走る女性。Stable Diffusion用のプロンプトを英語で出してください。"}
    ]
)

prompt_text = chat_response.choices[0].message.content
print("Generated Prompt:\n", prompt_text)

# Stable Diffusion APIへのリクエスト
sd_api = "https://bjtv1kzq2yhcnn-3001.proxy.runpod.net/sdapi/v1/txt2img"
# payload = {
#     "prompt": prompt_text,
#     "negative_prompt": "blurry, bad anatomy, lowres, ugly, watermark, cropped, distorted face",
#     "steps": 30,
#     "cfg_scale": 7.5,
#     "width": 768,
#     "height": 1152,
#     "sampler_index": "DPM++ 2M Karras"
# }

payload = {
    "prompt": "a beautiful girl in the forest, high quality, 8k",
    "negative_prompt": "blurry, low quality",
    "width": 512,
    "height": 512,
    "steps": 20,
    "cfg_scale": 7
}


res = requests.post(sd_api, json=payload)

print("Status Code:", res.status_code)

try:
    print("Response JSON:", res.json())
except Exception as e:
    print("Error parsing JSON:", e)
    print("Raw Response Text:", res.text)


image_base64 = res.json()["images"][0]

# Base64 → 画像保存
image = Image.open(BytesIO(base64.b64decode(image_base64)))
image.save("gpt2sd_output.jpg")
print("画像生成完了：gpt2sd_output.jpg")

