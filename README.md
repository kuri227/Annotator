# Annotator

画像と音声の分類教師データを効率よく作成する、Windows向けデスクトップアノテーションツールです。単一ラベルとマルチラベルの両方に対応し、1つの画像・音声へ複数のクラスを付与できます。

## ダウンロードと起動

Python環境を用意せずに利用する場合は、リポジトリ内の[Annotator.exe](dist/Annotator.exe)をダウンロードして起動してください。

- 対応OS: Windows 10 / 11（64bit）
- 現在のバージョン: 5.3.0
- インストール: 不要
- 実行ファイルは未署名のため、初回起動時にWindowsの警告が表示される場合があります。

ソースコードから起動する場合:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

## 主な機能

### 画像・音声の共通機能

- 画像分類と音声分類の切り替え
- 1ファイルに複数クラスを付与するマルチラベルアノテーション
- 数字キーによる高速なラベル選択・解除
- 前後移動、保留、保存のショートカット
- CSV / JSON形式でのアノテーション保存
- 従来の単一ラベルCSV / JSONの読み込み
- `raw_data`以下のサブフォルダを再帰的に検出
- 相対パス管理による同名ファイルの衝突防止
- ラベル済みファイルを`input_data`へ元の階層構造のままコピー
- 分類済み・未分類ファイルの一覧、絞り込み、20件単位のページング
- 一覧から任意のファイルへ直接移動

### 音声アノテーション

- WAV / MP3 / FLAC / OGG / M4A / AACの検出・再生
- PCM WAVの波形表示
- 波形クリックとシークバーによる再生位置移動
- 5秒送り・5秒戻し
- 再生速度と音量の変更
- ファイル選択時の自動再生
- 大容量ファイルのロードインジケーター、経過秒数、取得可能な場合の進捗率表示
- ロード中も前後のファイルへ移動可能
- 波形解析のバックグラウンド処理
- 破損・特殊ヘッダーを持つWAVの読み込み量制限

## 基本的な使い方

1. `Annotator.exe`または`app.py`を起動します。
2. 「画像分類」または「音声分類」を選択します。
3. プロジェクトフォルダを選択します。
4. 必要に応じて`raw_data`、`input_data`、アノテーション保存先を変更します。
5. クラス名をカンマ区切りで入力します（最大10クラス）。
6. 「アノテーションを開始」を押します。
7. 数字キーでラベルを選択し、`Enter`で確定して次へ進みます。
8. `Ctrl+S`で保存します。

## ショートカット

| キー | 動作 |
|---|---|
| `1`〜`9`, `0` | 対応するラベルの選択・解除 |
| `Enter` | 選択中のラベルを確定して次へ |
| `←` / `→` | 前後のファイルへ移動 |
| `S` | ラベルを変更せず次へ |
| `Ctrl+S` | アノテーションを保存 |
| `Space` | 音声の再生・一時停止 |
| `J` / `L` | 音声を5秒戻す・進める |

## 利用者のプロジェクト構成

アプリで扱うデータセットは、リポジトリとは別のプロジェクトフォルダで管理することを推奨します。

```text
my_annotation_project/
├─ raw_data/          # 未加工の画像・音声。サブフォルダも使用可能
├─ input_data/        # ラベル済みファイルの学習用コピー
└─ annotations/       # CSV / JSONのラベル情報
   ├─ image_labels.csv
   └─ audio_labels.csv
```

## GitHubリポジトリの構成

```text
Annotator/
├─ annotator/
│  ├─ __init__.py         # バージョン情報
│  ├─ diagnostics.py      # 例外境界と診断ログ
│  ├─ file_overview.py    # ファイル一覧、状態表示、ページング
│  ├─ main_window.py      # 設定画面とアノテーション画面
│  ├─ media_widgets.py    # 画像・音声ビューアと再生制御
│  ├─ models.py           # プロジェクトとセッションモデル
│  ├─ storage.py          # 検出、CSV/JSON保存、ファイルコピー
│  └─ waveform.py         # WAV波形解析と非同期描画
├─ dist/
│  └─ Annotator.exe       # 配布用Windows実行ファイル
├─ tests/
│  ├─ __init__.py
│  └─ test_core.py        # 保存、画像、音声、障害系の自動テスト
├─ .gitignore
├─ Annotator.spec         # PyInstaller設定
├─ app.py                 # アプリケーションのエントリーポイント
├─ build.ps1              # テストとEXEビルドの自動化
├─ requirements.txt       # 実行時依存関係
├─ requirements-dev.txt   # 開発・ビルド依存関係
└─ README.md
```

`.venv`、`build`、Pythonキャッシュ、利用者の画像・音声・アノテーションデータはGit管理対象外です。

## アノテーション形式

CSVは`filename,labels`の2列です。`labels`にはJSON配列を格納するため、日本語やカンマを含むラベルも安全に保存できます。

```csv
filename,labels
animals/sample.wav,"[""Dog"", ""Cat""]"
```

JSONではファイル名をキー、ラベル配列を値として保存します。

```json
{
  "animals/sample.wav": ["Dog", "Cat"]
}
```

以前の`filename,label`形式のCSVと、値が単一文字列のJSONも読み込めます。

## 安全性と障害時の動作

- UIイベント内の予期しないPython例外を捕捉し、可能な限り操作を継続します。
- アノテーションは一時ファイルへ書き出してから原子的に置換します。
- コピー失敗はファイル単位で隔離し、ラベル保存を継続します。
- 破損・非対応音声は再生領域へエラーを表示します。
- 音源切り替え時に同期停止を行わず、FFmpegによるUI停止を防ぎます。
- 診断ログは`%LOCALAPPDATA%\Annotator\logs\annotator.log`へ最大1MB、2世代で保存します。
- 通常の操作履歴やアノテーション内容は診断ログへ記録しません。

## 開発・テスト

Python 3.10〜3.12を推奨します。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -v
```

テストでは実際に一時CSV、PNG、WAVを生成し、マルチラベル保存、旧形式互換、波形解析、音声切替、異常ファイル、原子的保存を検証します。

## Windows EXEの作成

```powershell
.\build.ps1
```

全テストの成功後、PyInstallerがコンソール非表示の単体実行ファイル`dist\Annotator.exe`を生成します。生成後はEXEを実起動し、Gitへ追加する前に動作確認してください。
