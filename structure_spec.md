# 動画自動生成プロジェクト：構造仕様書（structure.md）

## ✅ 全体概要

本プロジェクトは、GPTで生成された台本JSONをもとに、音声、画像、字幕を全自動生成し、ffmpegでショート動画を合成する構成をとる。タイトル生成およびサムネ動画生成も独立工程として管理され、完全自動化と構造の拡張性を両立させている。

---

## ✅ ディレクトリ構成

```
project_root/
├─ generator/                  # 各自動生成モジュール群
│  ├─ tag_generator.py             ← GPTタグ補完 or 辞書タグ補完（将来用）
│  ├─ generate_audio.py            ← CoeFontによる音声生成 + timing.json出力
│  ├─ generate_subtitles.py       ← テロップファイル(srt/json)生成（tagsで色分け）
│  ├─ fetch_images.py             ← global_tags + tagsベースで画像検索（Pixabay or SD）
│  ├─ compose_video.py            ← ffmpegで最終合成（静止画＋音声＋字幕）
│  └─ title_generator.py          ← タイトル案生成（Step4）用APIまたはGPTローカル呼び出し
│
├─ thumbnail/                 # サムネ動画用の別処理構成
│  ├─ generate_thumbnail_script.py
│  ├─ generate_thumbnail_audio.py
│  └─ generate_thumbnail_video.py
│
├─ data/
│  ├─ scripts_ok/YYYYMMDD/*.json     ← GPT台本（tags付きチャンク構造）
│  ├─ scenes_json/YYYYMMDD/*.json    ← audioと同期後のtiming付き台本
│
├─ audio/000001/             # 台本1件分の音声ファイル群
├─ images/000001/            # scene_idごとの静止画
├─ subtitles/000001/         # srt/json形式の字幕
├─ output/000001/            # 最終動画（final.mp4）
│
├─ prompts/                  # GPTプロンプト雛形保管
├─ config/                   # APIキーや話速など設定ファイル
├─ common/                   # 各スクリプト間で使う共通処理群
├─ backup/                   # スクリプトの自動バックアップ保存先
├─ main_pipeline.py          # 全自動パイプライン呼び出し（進捗管理付き）
└─ .env / .gitignore
```

---

## ✅ 台本JSON仕様

```json
{
  "global_tags": ["恋愛", "焦り", "暗さ"],
  "script": [
    {
      "text": "（なんで目を逸らすの？）",
      "tags": ["恋愛", "違和感"],
      "scene_id": "scene_001"
    },
    ...
  ]
}
```

* `global_tags`：動画全体のトーン指定（画像選定の統一性確保）
* `tags`：チャンクごとの感情・意味付け（画像検索・音声表現・色分けに使用）
* `scene_id`：同じ画像でまとめる単位（5〜10秒程度）
* 後続処理にて `start_sec` / `end_sec` が付加される

---

## ✅ 処理フロー（台本 → 動画）

1. GPT台本生成（手動）

   * tags, scene\_id, global\_tagsを含むチャンク形式で保存（scripts\_ok）

2. `generate_audio.py`

   * CoeFont APIで音声出力
   * チャンクごとに音声を作成 → 音声長を記録し `start_sec` / `end_sec` を付加
   * 出力：`audio/000001/*.wav`, `scenes_json/*.json`

3. `fetch_images.py`

   * 各scene\_idに対して `global_tags + tags` をもとに画像検索
   * 画像が見つからない場合はフォールバック検索（タグを減らす）
   * 出力：`images/000001/*.jpg`

4. `generate_subtitles.py`

   * 各チャンクに対して字幕を生成
   * `tags`に応じた色分けも対応予定
   * 出力：`subtitles/000001/subtitles.srt`

5. `compose_video.py`

   * ffmpegで画像・音声・字幕を合成
   * 出力：`output/000001/final.mp4`

6. サムネ動画（任意）

   * `title_generator.py` でタイトルを生成
   * thumbnailモジュールで5秒動画を生成（画像＋ナレーション＋テロップ）

---

## ✅ 今後の拡張予定

* テロップのタグ別色分けルールを辞書化し、スクリプトから自動着色
* `tags`を用いた話速・抑揚制御（CoeFont APIパラメータ連携）
* `scene_id`内で複数画像を順に切り替える構成にも対応
* `main_pipeline.py` の実行ログとエラー通知を自動で保存（log/ディレクトリ化）
* タイトル案から自動サムネ画像作成（Midjourney or SD連携）
