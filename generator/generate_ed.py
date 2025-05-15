from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
from pathlib import Path
from script_utils import find_oldest_script_id

# --- 設定 ---
SCRIPT_DIR = Path("ed_ok")
SCRIPT_ID = find_oldest_script_id(SCRIPT_DIR)
INPUT_TEXT_PATH = SCRIPT_DIR / f"{SCRIPT_ID}.txt"
BACKGROUND_PATH = "fixed assets/background.jpg"  # 入力画像（要手動配置）
OUTPUT_DIR = "images/ed"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 36
TEXT_COLOR = (255, 255, 255)
IMAGE_SIZE = (1080, 1920)  # YouTubeショートに最適な縦長サイズ
TEXT_WRAP_WIDTH = 45

# --- テキスト読み込み＆分割 ---
with open(INPUT_TEXT_PATH, "r", encoding="utf-8") as f:
    raw_text = f.read()
blocks = [block.strip() for block in raw_text.strip().split("\n\n") if block.strip()]
text_blocks_1 = blocks[:3]
text_blocks_2 = blocks[3:] + ["＼チャンネル登録で、あなたの恋愛リテラシーが1UP／"]

texts = [text_blocks_1, text_blocks_2]

# --- 出力ディレクトリ ---
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 画像生成関数 ---
def generate_image(text_blocks, output_path):
    bg = Image.open(BACKGROUND_PATH).convert("RGB").resize(IMAGE_SIZE)
    draw = ImageDraw.Draw(bg)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    x, y = 60, 60
    for block in text_blocks:
        wrapped_lines = textwrap.wrap(block, width=TEXT_WRAP_WIDTH)
        for line in wrapped_lines:
            draw.text((x, y), line, font=font, fill=TEXT_COLOR)
            y += FONT_SIZE + 10
        y += 30

    bg.save(output_path)

# --- 実行 ---
for idx, text_group in enumerate(texts):
    filename = os.path.join(OUTPUT_DIR, f"{SCRIPT_ID}_ed_image_{idx+1}.png")
    generate_image(text_group, filename)
    print(f"Saved: {filename}")
