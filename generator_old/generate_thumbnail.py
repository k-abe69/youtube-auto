import os
import json
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import random
import requests
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from moviepy.editor import ImageClip, AudioFileClip
import imagehash
from dotenv import load_dotenv
from common.video_export import export_video_high_quality
from common.script_utils import extract_script_id, find_oldest_script_id, resolve_script_id 


load_dotenv()

# === 設定 ===
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
DURATION = 3
FONT_PATH = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
FONT_SIZE = 100
TEXT_COLOR = "white"
OUTLINE_COLOR = "black"
OUTLINE_WIDTH = 4
SE_PATH = Path("fixed assets/se_pop.mp3")
OUTPUT_DIR = Path("data/thumbnails")
INPUT_DIR = Path("thumbnails")
TAG_DIR = Path("data/stage_2_tag")
TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
assert PIXABAY_API_KEY, "Pixabay APIキーが未設定です"

# === テキスト合成関数 ===
def draw_text_centered(image: Image.Image, text: str, wrap_width: float = 18) -> Image.Image:
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    def visual_width(c): return 0.5 if c.isascii() else 1

    # 手動改行を尊重しながら、自動で折り返しを適用
    def wrap_paragraph(paragraph):
        lines = []
        current_line = ""
        width_count = 0
        for c in paragraph:
            width_count += visual_width(c)
            current_line += c
            if width_count >= wrap_width:
                lines.append(current_line)
                current_line = ""
                width_count = 0
        if current_line:
            lines.append(current_line)
        return lines

    # 全体の行リスト（手動改行を分割して処理）
    all_lines = []
    for para in text.split("\n"):
        all_lines.extend(wrap_paragraph(para))

    # 全体高さから縦中央位置を算出
    line_spacing = 20
    total_height = len(all_lines) * (font.size + line_spacing) - line_spacing
    y = (VIDEO_HEIGHT - total_height) // 2

    for line in all_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_w) // 2

        # アウトライン（影）付き描画
        for dx in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
            for dy in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=OUTLINE_COLOR)
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)
        y += font.size + line_spacing

    return image


# === Pixabay画像取得関数（類似画像除外つき）===
def fetch_striking_image(tags: list, save_to: Path) -> Path:
    query = "+".join(tags)
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={query}&image_type=photo&orientation=vertical&per_page=10"
    res = requests.get(url)
    if res.status_code != 200:
        raise RuntimeError(f"Pixabay APIエラー: {res.text}")
    
    data = res.json()
    hits = data.get("hits", [])
    used_hashes = set()

    for hit in hits:
        image_url = hit["largeImageURL"]
        try:
            img_data = requests.get(image_url).content
            img = Image.open(BytesIO(img_data)).convert("RGB")
            hash_val = imagehash.phash(img)
            if any(abs(hash_val - h) <= 5 for h in used_hashes):
                continue
            img.save(save_to)
            return save_to
        except Exception as e:
            print(f"画像取得エラー: {e}")
            continue

    raise RuntimeError("該当する画像が見つかりませんでした")

# === メイン処理 ===
def generate_thumbnail_video(script_id: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tag_path = TAG_DIR / f"tags_{script_id}.json"
    if not tag_path.exists():
        raise FileNotFoundError(f"タグファイルが見つかりません: {tag_path}")
        # === テキスト読み込み（追加） ===
    txt_path = INPUT_DIR / f"{script_id}.txt"
    if not txt_path.exists():
        raise FileNotFoundError(f"テキストファイルが見つかりません: {txt_path}")

    # タグ読み込み（そのまま）
    with open(tag_path, "r", encoding="utf-8") as f:
        tag_data = json.load(f)

    # テキスト読み込み（別ファイルを新たに開く）
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    tags = tag_data.get("global_image_tag", "")
    tags = [tags] if isinstance(tags, str) else (tags or ["abstract"])
    tmp_image = TMP_DIR / f"{script_id}_thumb.jpg"
    fetch_striking_image(tags, save_to=tmp_image)

    # 背景画像読み込み + テキスト合成
    original_img = Image.open(tmp_image).convert("RGB")
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), "black")
    canvas.paste(original_img.resize((VIDEO_WIDTH, VIDEO_HEIGHT)))
    canvas = draw_text_centered(canvas, text)
    clip = ImageClip(np.array(canvas)).set_duration(DURATION)

    if SE_PATH.exists():
        audio = AudioFileClip(str(SE_PATH)).set_duration(DURATION)
        clip = clip.set_audio(audio)

    out_path = OUTPUT_DIR / f"{script_id}_thumb.mp4"
    export_video_high_quality(clip, str(out_path))
    print(f"✅ サムネ動画生成完了: {out_path}")

# 実行例
if __name__ == "__main__":
    script_id = resolve_script_id()
    if len(sys.argv) < 2:
        print("使い方: python generate_thumbnail_video.py <script_id>")
        exit(1)
    generate_thumbnail_video(sys.argv[1])
