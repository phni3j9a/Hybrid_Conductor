# 検証記録 — v0.2.0

実施日: 2026-10-08。Pi Main対応、共通初回モデル設定、Checkpoint復帰を追加。

| 検証 | 結果 |
|---|---|
| `python3 -m unittest discover -s tests -v` | 48件成功、失敗0、skip 0 |
| Pythonコンパイル / `git diff --check` | 成功 |
| herdr初回設定 | defaultsだけで未設定、全役割の既存明示設定で完了、部分設定・層別優先順位を検証 |
| Pi初回設定 | native namespace・全5役割・Project優先・thinking任意/false・無効設定・read-onlyを検証 |
| pi-subagents native parser | 全5Agentのnamespace、Fresh、context flags、空extensions、Reviewer allowlistを確認 |
| Skillとパッケージ | 3Skillのfrontmatter・相対リンク、Pi公開Skill/Agent pathsを検証 |
| Codex installer / herdr bootstrap | 既存の隔離fixtureテストが成功 |
| 認証済みPiでの委任・再開・レビュー | 未検証。実行CLI・認証環境なし |
| herdrでの委任・レビュー | 下記の実機検証を参照。v0.2.0の初回モデル設定を含む版では未実行 |

ログ: [test-output.txt](test-output.txt)。native parserはnicobailon/pi-subagents
commit `0c33ec7cb26ed1db270d72e746c3c975be880aeb`（package版0.76.1）に対して確認。
これはPi上でのAgent discovery・モデル利用・セッション復帰の実機検証ではない。

```bash
node --experimental-strip-types tests/verify_pi_agents.mjs /path/to/pi-subagents
```

[実機シナリオ](../tests/scenarios.md) に従い、インストール済みバージョンで
Agent discovery、認証済みprovider、実効model/thinking/tools、Fresh/Resume、再起動復帰を確認する。
未対応のmaxや取得できないrun IDのfallbackも対象。herdr接続は導入版 `herdr --skill` が基準。

## herdr実機検証 — 2026-10-05（v0.1 + 起動テンプレート）

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

## herdr実機での再検証 — 2026-10-06

上記の対処を入れたPR版（`--plugin-dir` でworktreeを指定）で、同じ依頼を `/tmp` の外の使い捨てリポジトリに対して実行した。
依頼文では権限・受け渡し方法・レイアウトを指定せず、「子agentは承認なしで起動してよい」とだけ伝えた。

| 項目 | 結果 |
|---|---|
| 開始時の確認 | 子agentの起動前に、mainがCodexのフォルダ信頼と `.hybrid-conductor/` の除外方法をユーザーに確認した |
| レイアウト | mainが左40%（幅140中56）、子agentが右60%。2体目以降は子のpaneだけを下・右と交互に分割 |
| pane名 | `hc-planner` などのラベルが付き、plannerのpaneを `hc-worker-core` に再利用したときも付け替えた |
| 権限 | planner・reviewerは `-C <run>/agents/<agent名>` で起動し、製品側に余分なファイルはなかった。`/status` は全員 `Workspace (never)` |
| 受け渡し | 4体とも `agents/<agent名>/<タスクID>.md` に報告を書いた（計画121行、レビュー53行）。mainは計画を書き写さず、パスで渡した |
| レビュー | 初回でPASS（指摘なし）。reviewerは既存テスト15件に加え、独自の36ケースを確認した |
| 後片付け | 子agentとpaneを終了。Codexの信頼設定はバックアップと同一に戻した |
| 呼び出し | mainのツール呼び出しは42回（前回47回）。起動の再試行はなく、エラー2件は終了後の読み取りなど軽微なもの |

この回ではoh-my-zshの更新確認が出なかったため、プロンプト待ちの手順の効果は確認できていない。
mainは「並列実行中のworkerが `__pycache__` を削除した」ことを指摘した。→ 並列中の生成物削除の禁止を進行方針に追記。
幅42のpaneでは `/status` の表示が折り返され、読み取りに手間がかかった。

## herdrで残る検証

v0.2.0の初回モデル設定（`--check-setup`）を含む版での実行、子として起動するClaude Code（designerなど）と、そのモデル・effort・権限モードの実効値、
停滞時の方法変更、ユーザー停止への応答、[実機シナリオ](../tests/scenarios.md) の未実行項目は実機で検証する必要がある。

方針はSkillへの指示であり、強制runtimeやOS sandboxを追加したものではない。
