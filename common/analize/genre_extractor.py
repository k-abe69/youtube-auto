import os
import json

# 共通関数：スクリプトIDをファイル名から取得
def extract_script_id(file_path: str) -> str:
    base_name = os.path.basename(file_path)
    return os.path.splitext(base_name)[0]

# メタ情報作成関数
def generate_meta_json(file_path: str, output_dir: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # スクリプトID
    script_id = extract_script_id(file_path)

    # 大タイトル抽出（最初のブロックを仮定）
    title_line_idx = next(i for i, line in enumerate(lines) if line.strip() == '[大タイトル]')
    main_title = lines[title_line_idx + 1].strip().strip('“”"')

    # ジャンル（後でGPTで判定する想定）
    genre = "UNKNOWN"

    # メタ情報辞書
    meta = {
        "script_id": script_id,
        "main_title": main_title,
        "genre": genre
    }

    # 出力
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{script_id}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"メタファイル生成: {output_path}")

# 使用例（仮パス）
generate_meta_json("script_20250528_01.txt", "./meta_output")
