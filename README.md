# LED Matrix Software

16ピクセル高のLEDマトリックスディスプレイ（128x16）を制御するPythonソフトウェアです。

## 特徴

- **複数のフォント対応**
  - Shinonomeフォント（推奨）: 豊富な日本語文字、ひらがな、カタカナ、漢字対応
  - Chara Zenkakuフォント: 全角文字対応

- **複数の出力デバイス対応**
  - シリアルデバイス: 実際のLEDマトリックス（シリアル接続）
  - ターミナル出力: ハードウェアなしでテスト可能
  - 画像出力: staticモードではPNG画像、scrollモードではMP4動画として保存
    - リアルなLED表示: グロー効果付きの丸いLED描画（1280x200ピクセル、上下ボーダー付き）

- **表示モード**
  - 静的表示: テキストを固定表示
  - スクロール表示: テキストを右から左にスクロール
  - **ダッシュボードモード**: 東京都目黒区駒場の天気予報と京王本線／京王井の頭線／千代田線／小田急線の遅延情報を非同期でスクレイピングしてスクロール表示。警報・注意報は反転フラッシュ＋低速スクロールで強調。

## インストール

### 前提条件

- Python 3.11以上
- uv（推奨）

### uvを使用したインストール

```bash
# 依存関係のインストール
uv sync

# 開発モードでインストール
uv pip install -e .
```

### 通常のpipを使用したインストール

```bash
pip install -e .
```

## 使い方

### 基本的な使い方

```bash
# ターミナルでテキストを表示（デフォルト）
uv run python -m led_matrix_software.main --text "こんにちは"

# スクロール表示
uv run python -m led_matrix_software.main --mode scroll --text "LEDマトリックスディスプレイ"

# 静的表示を画像として保存（PNG形式）
uv run python -m led_matrix_software.main --device image --text "Hello LED"

# スクロール表示を動画として保存（MP4形式）
uv run python -m led_matrix_software.main --device image --mode scroll --text "テスト"
```

### シリアルデバイスの使用

```bash
# Windows (COM5)
uv run python -m led_matrix_software.main --device serial --port COM5 --text "Hello"

# Linux/Mac
uv run python -m led_matrix_software.main --device serial --port /dev/ttyUSB0 --text "Hello"
```

### フォントの選択

```bash
# Shinonomeフォント（デフォルト）
uv run python -m led_matrix_software.main --font shinonome --text "東京スカイツリー"

# Chara Zenkakuフォント
uv run python -m led_matrix_software.main --font chara_zenkaku --text "あけましておめでとう"
```

### ダッシュボードモード

ダッシュボードモードは非同期実行のMailLoopとして動作し、天気予報と電車遅延情報をスクロールします。

```bash
# ターミナルシミュレータでテスト
uv run python -m led_matrix_software.main --mode dashboard --device terminal

# 実機シリアル (COM5)
uv run python -m led_matrix_software.main --mode dashboard --device serial --port COM5

# 動画として保存（MP4）
uv run python -m led_matrix_software.main --mode dashboard --device image --output-dir output/dashboard

# 取得間隔とスクロール速度をカスタマイズ
uv run python -m led_matrix_software.main --mode dashboard --device terminal \
    --weather-interval 300 --train-interval 30 \
    --scroll-speed 0.02 --alert-scroll-speed 0.05
```

#### ダッシュボードモードの動作

1. **天気予報スクレイパ** (tenki.jp目黒区)
   - 10分間隔で「今日」セクションを取得 (`--weather-interval` 秒)
   - 天気、最高/最低気温、現在の湿度を抽出
   - `警報・注意報` ページから東京都に発表中の警報・注意報を抽出

2. **電車遅延スクレイパ** (Yahoo!乗換案内)
   - 60秒間隔で4路線の運行状況を取得 (`--train-interval` 秒)
   - 対象路線: 京王本線 / 京王井の頭線 / 小田急小田原線 / 東京メトロ千代田線
   - 並列取得 (ThreadPoolExecutor)

3. **非同期MailLoop**
   - メインスレッド: 天気予報をスクロール → 1周期終了時に「新着の遅延割り込み」があれば運行情報スクロールを挿入
   - バックグラウンドスレッド: スクレイパを定期実行し、`DashboardState` (threading.Lock) を更新

4. **警報・注意報の強調表示**
   - 該当文字列を `！注意報！` で囲む
   - スクロール中の警報区間フレームを **反転（背景ON/文字OFF）** に交互切り替えでフラッシュ再生
   - 通常 0.02s/frame → 警報区間 0.04s/frame に減速

5. **フォント制約**
   - ダッシュボードモードは Shinonome 固定（天気・注意報に必要な漢字/記号が揃うため）
   - `--font chara_zenkaku` を指定するとエラー終了

### コマンドラインオプション

```
--device {serial,terminal,image}  出力デバイスタイプ（デフォルト: terminal）
--port PORT                       シリアルポート（デフォルト: COM23）
--baudrate BAUDRATE               ボーレート（デフォルト: 921600）
--font {shinonome,chara_zenkaku}  使用するフォント（デフォルト: shinonome）
--font-dir FONT_DIR               フォントディレクトリパス
--mode {static,scroll,loop,dashboard}  表示モード（デフォルト: static）
--text TEXT                       表示するテキスト
--scroll-speed SPEED              スクロール速度（秒）（デフォルト: 0.02）
--output-dir OUTPUT_DIR           画像出力ディレクトリ（デフォルト: output）
--weather-interval SECONDS        dashboard: 天気取得間隔（デフォルト: 600）
--train-interval SECONDS          dashboard: 電車取得間隔（デフォルト: 60）
--alert-scroll-speed SECONDS      dashboard: 警報区間のスクロール遅延（デフォルト: 0.04）
```

## プロジェクト構造

```
led-matrix-software/
├── src/
│   └── led_matrix_software/
│       ├── __init__.py
│       ├── main.py              # メインエントリーポイント
│       ├── matrix.py            # マトリックスバッファ変換
│       ├── devices/             # デバイスモジュール
│       │   ├── __init__.py
│       │   ├── base.py          # デバイス基底クラス
│       │   ├── serial_device.py # シリアルデバイス
│       │   └── simulator.py     # シミュレータ（ターミナル/画像）
│       ├── fonts/               # フォントモジュール
│       │   ├── __init__.py
│       │   ├── base.py          # フォント基底クラス
│       │   ├── shinonome.py     # Shinonomeフォント
│       │   └── chara_zenkaku.py # Chara Zenkakuフォント
│       └── dashboard/           # ダッシュボードモード
│           ├── __init__.py
│           ├── state.py         # スレッドセーフな共有状態
│           ├── weather.py       # tenki.jp 天気スクレイパ
│           ├── trains.py        # Yahoo!乗換案内 電車スクレイパ
│           ├── renderer.py      # 表示テキスト生成 + 強調フレーム列
│           └── mail_loop.py     # 非同期メインループ
├── shinonome16-1.0.4/           # Shinonomeフォントデータ
├── chara_zenkaku/               # Chara Zenkakuフォントデータ
├── pyproject.toml               # プロジェクト設定
└── README.md
```

## LEDマトリックス仕様

- **解像度**: 128 x 16 ピクセル
- **通信**: シリアル通信（921600 bps）
- **プロトコル**: Base64エンコードされた256バイト（uint16配列[8][16]）
- **ファームウェア**: [LED_Matrix_firmware_K00798](https://github.com/KikuchiMakoto/LED_Matrix_firmware_K00798)

### 画像出力の特徴

- **出力サイズ**: 1280 x 200 ピクセル（10倍スケール + 上下20pxボーダー）
- **LED描画**: グロー効果付きの丸いLED表示（直径約8-9ピクセル）
- **色**: 赤色LED（中心が明るく、外側に向かってグラデーション）
- **背景**: 黒色（実際のLEDマトリックスを再現）

## 開発

### テスト実行

```bash
# ターミナルシミュレータでテスト
uv run python -m led_matrix_software.main --device terminal --text "テスト"

# ダッシュボードモードのテスト（オフライン時は天気/電車取得失敗の表示が出る）
uv run python -m led_matrix_software.main --mode dashboard --device terminal
```

### コードフォーマット

```bash
uv run black src/
uv run ruff check src/
```

## ライセンス

このプロジェクトは個人使用を目的としています。
