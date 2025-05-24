from PIL import Image, ImageDraw, ImageFont
import textwrap
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pathlib import Path
from common.script_utils import find_oldest_script_id, resolve_script_id 
from moviepy.editor import ImageClip, concatenate_videoclips
from common.video_export import export_video_high_quality

# === 基本設定 ===
SCRIPT_DIR = Path("ed_ok")
OUTPUT_DIR = Path("data/ed")
BG_PATH = Path("fixed assets/background.jpg")
FONT_PATH_TITLE = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
FONT_PATH_BODY = "C:/Windows/Fonts/NotoSansJP-Regular.ttf"
FONT_SIZE_TITLE = 52
FONT_SIZE_BODY = 40
IMAGE_SIZE = (1080, 1920)
TEXT_LEFT_MARGIN = 40
TEXT_RIGHT_MARGIN = 80
TEXT_COLOR_TITLE = (255, 255, 100)
TEXT_COLOR_BODY = (255, 255, 255)
OUTLINE_COLOR = "black"
OUTLINE_WIDTH = 2
WRAP_TITLE = 26
WRAP_SOURCE = 26
BLOCK_SPACING = 50
TITLE_TOP_Y = 80

# === 拡張設定 ===
HEADER_TEXT = "📊 研究出典まとめ"
FOOTER_TEXT = "Some images provided by Unsplash"


def generate_ed_video(script_id: str, image_dir: Path, output_path: Path, duration_per_image: float = 3.5):
    # 該当画像を取得（昇順ソート）
    image_files = sorted(image_dir.glob(f"{script_id}_ed_*.png"))
    if not image_files:
        print("❌ ED画像が見つかりません")
        return

    # 各画像をクリップ化（同一時間）
    clips = [
        ImageClip(str(img)).set_duration(duration_per_image)
        for img in image_files
    ]
    final_clip = concatenate_videoclips(clips, method="compose")
    export_video_high_quality(final_clip, str(output_path))
    print(f"✅ ED動画を生成しました: {output_path}")


# 半角＝0.5文字、全角＝1文字とみなして折り返す関数
def visual_wrap(text, max_width):
    lines = []
    current_line = ""
    current_len = 0
    for ch in text:
        unit = 0.5 if ch.isascii() else 1
        if current_len + unit > max_width:
            lines.append(current_line)
            current_line = ch
            current_len = unit
        else:
            current_line += ch
            current_len += unit
    if current_line:
        lines.append(current_line)
    return lines

# 改良版：見た目幅ベースで折り返すアウトライン付き描画関数
def draw_text_with_outline(draw, text, font, x, y, wrap_width, fill, outline_color="black", outline_width=2):
    lines = visual_wrap(text, max_width=wrap_width)
    for line in lines:
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=font, fill=outline_color)
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + 10
    return y + 20

# === 横線（区切り線）描画関数 ===
def draw_horizontal_line(draw, y, color=(200, 200, 200), margin=TEXT_LEFT_MARGIN):
    draw.line((margin, y, IMAGE_SIZE[0] - margin, y), fill=color, width=2)

# === メイン処理関数 ===
def generate_ed_from_txt(txt_path: Path, output_dir: Path, script_id: str):
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # テキストを3行ごとのブロックに変換
    blocks = []
    for i in range(0, len(lines), 3):
        blocks.append({
            "title": f"{int(i / 3) + 1}．{lines[i]}",
            "source": lines[i + 1],
        })

    # フォント読み込み
    font_title = ImageFont.truetype(FONT_PATH_TITLE, FONT_SIZE_TITLE)
    font_body = ImageFont.truetype(FONT_PATH_BODY, FONT_SIZE_BODY)

    # 背景画像読み込み
    bg = Image.open(BG_PATH).convert("RGB").resize(IMAGE_SIZE)

    os.makedirs(output_dir, exist_ok=True)

    # 3件ずつ1ページとして処理
    for page_num in range((len(blocks) + 2) // 3):
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        x, y = TEXT_LEFT_MARGIN, TITLE_TOP_Y

        # === ページ上部タイトル（固定文） ===
        y = draw_text_with_outline(draw, HEADER_TEXT, font_title, x, y, wrap_width=WRAP_TITLE, fill=TEXT_COLOR_TITLE)
        y += 30  # タイトル下マージン

        # === 各ブロック描画 ===
        start = page_num * 3
        end = min(start + 3, len(blocks))
        for idx, block in enumerate(blocks[start:end]):
            y = draw_text_with_outline(draw, block["title"], font_title, x, y, WRAP_TITLE, TEXT_COLOR_TITLE)
            y = draw_text_with_outline(draw, block["source"], font_body, x, y, WRAP_SOURCE, TEXT_COLOR_BODY)
            y += BLOCK_SPACING
            if idx < 2:  # 最後のブロック以外に区切り線
                draw_horizontal_line(draw, y - int(BLOCK_SPACING / 2))

        # === ページ下部クレジット文（固定） ===
        footer_y = IMAGE_SIZE[1] - 100
        draw_text_with_outline(draw, FOOTER_TEXT, font_body, x, footer_y, wrap_width=WRAP_SOURCE, fill=TEXT_COLOR_BODY)

        # === 保存処理 ===
        out_path = output_dir / f"{script_id}_ed_{page_num + 1}.png"
        img.save(out_path)
        print(f"✅ Saved: {out_path}")

# === 実行ブロック：引数あり or 自動選択 ===
if __name__ == "__main__":
    script_id = resolve_script_id()

    txt_path = SCRIPT_DIR / f"{script_id}.txt"
    if not txt_path.exists():
        print(f"❌ 入力テキストが見つかりません: {txt_path}")
        exit()

    print(f"📄 入力スクリプトID: {script_id}")
    print(f"📥 テキストファイル: {txt_path}")
    generate_ed_from_txt(txt_path, OUTPUT_DIR, script_id)
    # 動画も出力（4秒前後を想定）
    video_output_path = Path(f"data/ed/{script_id}_ed_video.mp4")
    generate_ed_video(script_id, image_dir=OUTPUT_DIR, output_path=video_output_path)
