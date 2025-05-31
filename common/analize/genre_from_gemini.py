import os
import json
import re

def extract_metadata(filepath):
    """
    Extracts metadata from a Japanese script file.

    Args:
        filepath (str): The path to the Japanese script file.

    Returns:
        dict: A dictionary containing the extracted metadata (script_id, main_title, genre),
              or None if the file cannot be processed.
    """
    metadata = {}

    # 1. Extract script_id from filename
    filename = os.path.basename(filepath)
    match_script_id = re.match(r'script_(\d+)\.txt', filename)
    if match_script_id:
        metadata['script_id'] = match_script_id.group(1)
    else:
        print(f"Warning: Could not extract script_id from filename: {filename}")
        metadata['script_id'] = "unknown"

    # 2. Extract main_title from content
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            main_title = None
            for line in lines:
                line = line.strip()
                if line.startswith("大タイトル"):
                    main_title = line.split("大タイトル")[1].strip()
                    break
            if main_title:
                metadata['main_title'] = main_title
            else:
                print(f"Warning: Could not find '大タイトル' in file: {filename}")
                metadata['main_title'] = "Unknown Title"
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

    # 3. Determine genre based on content (simple keyword matching)
    # This is a very basic approach. A more robust system would use NLP techniques.
    content_text = "".join(lines)
    genre_keywords = {
        "恋愛": ["恋愛", "恋", "愛", "デート", "結婚", "交際", "告白", "惚れ合う", "片思い"],
        "人体": ["人体", "体", "骨", "筋肉", "臓器", "細胞", "病気", "健康", "医学", "生理"],
        "社会": ["社会", "人々", "政治", "経済", "文化", "教育", "法律", "仕事", "生活", "環境"],
        "心理": ["心理", "心", "感情", "思考", "精神", "行動", "記憶", "学習", "モチベーション", "意識"]
    }

    genre_scores = {genre: 0 for genre in genre_keywords}

    for genre, keywords in genre_keywords.items():
        for keyword in keywords:
            if keyword in content_text:
                genre_scores[genre] += 1

    # Select the genre with the highest score
    if any(score > 0 for score in genre_scores.values()):
        determined_genre = max(genre_scores, key=genre_scores.get)
        metadata['genre'] = determined_genre
    else:
        print(f"Warning: Could not determine genre for file: {filename} based on keywords.")
        metadata['genre'] = "Unknown"

    return metadata

def process_script_files(input_dir, output_file):
    """
    Processes all .txt files in the input directory, extracts metadata,
    and saves it to a JSON file.

    Args:
        input_dir (str): The path to the directory containing the script files.
        output_file (str): The path where the metadata JSON will be saved.
    """
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory not found at {input_dir}")
        return

    all_metadata = []
    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(input_dir, filename)
            print(f"Processing: {filepath}")
            metadata = extract_metadata(filepath)
            if metadata:
                all_metadata.append(metadata)

    # Save the collected metadata to a JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved metadata to {output_file}")
    except Exception as e:
        print(f"Error saving metadata to {output_file}: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    input_directory = "data/stage_0_script"
    output_json_file = "metadata.json"

    # Create input directory if it doesn't exist
    if not os.path.exists(input_directory):
        os.makedirs(input_directory)
        # Create dummy script files for demonstration
        with open(os.path.join(input_directory, "script_20250529_03.txt"), "w", encoding="utf-8") as f:
            f.write("大タイトル：なぜ “いい人止まり” で終わるのか？\n")
            f.write("これは恋愛に関する脚本です。\n")
            f.write("デートや交際、感情について話します。\n")
        with open(os.path.join(input_directory, "script_20250529_04.txt"), "w", encoding="utf-8") as f:
            f.write("大タイトル：人体構造の不思議\n")
            f.write("これは人体や医学に関する脚本です。\n")
            f.write("臓器や細胞、健康について説明します。\n")
        with open(os.path.join(input_directory, "script_20250529_05.txt"), "w", encoding="utf-8") as f:
            f.write("大タイトル：現代社会の課題\n")
            f.write("これは社会や人々に関する脚本です。\n")
            f.write("政治、経済、文化について議論します。\n")
        with open(os.path.join(input_directory, "script_20250529_06.txt"), "w", encoding="utf-8") as f:
            f.write("大タイトル：人間の心理の深層\n")
            f.write("これは心理学に関する脚本です。\n")
            f.write("感情や思考、行動について探求します。\n")
        with open(os.path.join(input_directory, "script_20250529_07.txt"), "w", encoding="utf-8") as f:
            f.write("大タイトル：混合ジャンルの話\n")
            f.write("これは複数のテーマが混ざった脚本です。\n")
            f.write("恋愛、社会、心理的な要素に触れます。\n")


    process_script_files(input_directory, output_json_file)