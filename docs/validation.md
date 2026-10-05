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

## 実機検証 — 2026-10-05

環境: Ubuntu 24.04 / zsh（oh-my-zsh）、Python 3.12.3、herdr 0.9.3（server 0.9.1）、
codex-cli 0.160.0、Claude Code 2.1.289。使い捨てのgitリポジトリで、標準ライブラリだけのPythonパッケージ
（集計関数4つ、CLI、unittest）の作成を `/hybrid-conductor:conduct` に依頼した。
依頼文では、plannerを使うこと、coreとCLIを別workerで並列化すること、独立reviewerを使うこと、
researcherとdesignerを使わないこと、子agentを書き込み可能・承認なしで起動してよいことを指定した。

| 項目 | 結果 |
|---|---|
| `claude plugin validate` | 成功。authorがないという警告1件のみ |
| bootstrap | exit 0。`herdr --skill` のガイド214行を取得 |
| Claude Code / Codexでのskill認識 | 両方で `conduct` と `herdr-adapter` を認識 |
| main（Claude Code、`--plugin-dir`） | `herdr --skill` を読み、設定を解決した。herdrの操作で構文の誤用はほぼなかった |
| planner（gpt-6-astra / high） | 受け入れ条件AC-1〜7とファイル単位の担当を返し、mainが採用 |
| worker 2体（gpt-6-luna / max） | 並列に実装し、`agent wait` を並列にして回収 |
| reviewer（gpt-6.1-sol / high） | 新しいセッションで起動。初回はCHANGES_REQUESTED（テストの見逃し2件）、修正後の再レビューでPASS |
| 実効値の確認 | 各agentで `/status` を送り、モデル・effort・権限を確認 |
| 後片付け | mainが作成したagentとpaneを終了 |
| 所要時間・費用 | 約20分。main側の表示は $1.88。Codex側の消費量は未集計 |

mainのツール呼び出し47回のうち、約15回が起動まわりの再試行だった。主な原因と、この版での対処:

- 新しいpaneでoh-my-zshの更新確認が出て、起動コマンドの先頭が入力として食われた（3回）。
  → [起動の準備](../skills/herdr-adapter/references/launch.md) にプロンプト待ちを追記。
- `config.toml` の `default_permissions` により `-s workspace-write` が無視され、plannerが全権限で起動した。
  別途 `codex exec -s read-only` だけで起動すると `sandbox: danger-full-access` となり書き込めることも確認した。
  `-c default_permissions=":read-only"` を併用すると、`read-only file system` で書き込みが拒否された。
  → 権限の上書きを含む役割別テンプレートを追加。
- planner・researcher・reviewerを製品に書けない状態にする方法を `codex exec` で比較した（製品は `/tmp` の外に置いた）。
  `:read-only` + `--add-dir <報告先>` は報告先にも書けなかった。`-c permissions.<name>...` でその場で作った権限プロファイルは
  解釈されず、製品に書き込めた。`:workspace-write` で作業ルートを `<project>/.hybrid-conductor/runs/<run>/` にすると、
  書き込み範囲は作業ルート・`/tmp`・`$TMPDIR` になり、製品には書けず、runディレクトリには書けた。→ この方式を採用。
- Codexの未信頼フォルダ確認でstartがblockedになった。`-c projects."<path>".trust_level=...` では回避できず、
  mainが信頼を選んだため `~/.codex/config.toml` に記録が残った（検証後に削除）。→ ユーザーに確認する運用を明記。
- paneに役割名がなく、画面上で担当が分からなかった。→ `pane rename` で役割名のラベルを付ける運用を追加。
  ラベルは日本語も使えることを確認した。
- `pane split --ratio` は分割元のpaneが残す割合だった（幅200で0.6なら元120・新80）。→ mainを左40%に残す配置を既定にした。

## 実機で残る検証

子として起動するClaude Code（designerなど）と、そのモデル・effort・権限モードの実効値、
停滞時の方法変更、ユーザー停止への応答、[実機シナリオ](../tests/scenarios.md) の未実行項目は実機で検証する必要がある。

[実機受け入れシナリオ](../tests/scenarios.md) を同梱。
本版は方針を実行するskillパッケージであり、レビューの有限回収束や権限境界を強制するランナーではない。
