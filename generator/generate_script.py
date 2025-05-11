import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import os
import datetime
from dotenv import load_dotenv
import openai

from common.backup_script import backup_script
backup_script(__file__)
from common.save_config import save_config_snapshot
save_config_snapshot()

# APIキー読み込み
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_output_dir():
    today = datetime.datetime.now()
    path = os.path.join(
        "data", "scripts_raw",
        f"{today.year:04}",
        f"{today.month:02}",
        f"{today.day:02}"
    )
    os.makedirs(path, exist_ok=True)
    return path

def load_prompt(step_number):
    prompt_path = f"prompts/script/step_{step_number}_prompt.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def call_chatgpt(messages: list) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.8
    )
    return response.choices[0].message.content.strip()

def generate_single_script(script_id: int):
    messages = []
    outputs = {}

    for step in range(1, 5):
        base_prompt = load_prompt(step)
        if step == 1:
            user_prompt = base_prompt
        else:
            memory = ""
            for prev_step in range(1, step):
                memory += f"\n【Step {prev_step}の出力】\n{outputs[prev_step].strip()}\n"
            user_prompt = f"{memory}\nこの内容に基づいて、以下の指示に従ってください：\n{base_prompt}"

        messages.append({"role": "user", "content": user_prompt})

        print(f"\n--- Step {step} 実行中（ID: {script_id:06}） ---")
        print(f"[Prompt]:\n{user_prompt}\n")

        try:
            response = call_chatgpt(messages)
            messages.append({"role": "assistant", "content": response})
            outputs[step] = response
            print(f"\n✅ Step {step} 出力完了 ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓\n")
            print(response)
            input("\n⏎ Enterで次のステップへ進む ＞ ")
        except Exception as e:
            print(f"[エラー] Step {step} の出力に失敗: {e}")
            return None

    return outputs.get(3, "")  # Step3台本のみ保存

def generate_batch_scripts(count: int = 1):  # まずは1本ずつ確認
    output_dir = get_output_dir()
    for i in range(count):
        script_id = i + 1
        content = generate_single_script(script_id)
        if content:
            path = os.path.join(output_dir, f"{script_id:06}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ 台本 {script_id:06} を保存 → {path}")

if __name__ == "__main__":
    print("=== バズ台本セミオート生成モード（1本ずつ）開始 ===")
    generate_batch_scripts(count=1)
