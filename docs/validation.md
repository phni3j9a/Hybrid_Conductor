# 検証記録 — v0.1.0

実施日: 2026-10-05。環境: Linux / Python 3.13.5。
GitHubへの初回登録準備時に、配布ZIPを展開して自動テスト32件を再実行し、すべて成功した。
READMEの変更はclone手順と導入パスの追加のみで、skill・設定・補助処理は初版のまま。

## 実行結果

| 検証 | 結果 |
|---|---|
| `python3 -m unittest discover -s tests -v` | 32件成功、失敗0、skip 0 |
| Pythonファイルのコンパイル | 成功 |
| 設定のCLI解決 | 成功。既定モデル・effort・設定元をJSONで出力 |
| Skillの基本frontmatter・相対リンク | パッケージ内の独自構造テストで成功 |
| Codex用skill導入 | 一時ディレクトリへのsymlink作成・再実行・衝突・ロールバックを検証 |
| `herdr --skill` の直接実行 | 不可。`herdr: command not found`、exit 127 |
| 実環境でのbootstrap実行 | 想定どおりCLI未導入を報告、exit 2。セッション操作なし |
| Claude Code公式 `plugin validate` | 未実行。CLI未導入 |
| 実際のCodex / Claude Code起動 | 未実行。CLI・認証環境なし |
| 実モデルでの委任とレビュー収束 | 未検証 |

自動テストのログ: [test-output.txt](test-output.txt)。

## 自動テストの対象

設定の優先順位と部分マージ、任意モデル文字列、CodexからClaudeへの役割変更、
無効な設定・重複キー・欠落ファイル、設定値をコードとして実行しないことを確認。
レビュー回数上限の設定は存在せず、追加すると不明キーとして拒否される。

bootstrapは隔離されたfake executableまたはmockを使って検証。
`--skill`以外を呼ばないこと、環境外から続行しないこと、失敗・空出力・不正な文字コード・
タイムアウトで操作を進めないことを確認した。
タイムアウトのテストはプロセス起動のタイミングに依存しない方法へ修正済み。
これらのfake出力を、実際のherdr skillの取得結果として扱ってはいない。

共通入口は46行、herdr接続用skillは72行。詳細資料は必要時に読む参照ファイルへ分離。
構造テストは公式Plugin validatorや実行モデルの評価の代わりにはならない。

## 実機で残る検証

導入済みherdr版に対する `--skill` の読み込み、native CLIへのmodel/effortの指定と実効値、
pane上での並列タスク送信・結果回収、統合された対象での独立レビュー、
停滞時の方法変更、ユーザー停止への応答は実機で検証する必要がある。

[実機受け入れシナリオ](../tests/scenarios.md) を同梱。
本版は方針を実行するskillパッケージであり、レビューの有限回収束や権限境界を強制するランナーではない。
