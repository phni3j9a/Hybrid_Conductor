# モデルと設定

## 優先順位

今回の明示指定 > プロジェクト > ユーザー > Plugin既定値。

| 層 | 場所 |
|---|---|
| 既定値 | このskillの `assets/defaults.json` |
| ユーザー | `$XDG_CONFIG_HOME/hybrid-conductor/config.json`。未設定なら `~/.config/hybrid-conductor/config.json` |
| プロジェクト | プロジェクトルートの `.hybrid-conductor.json` |
| 今回の指定 | 会話での明示指定。再現性が必要なら一時JSONを `--overrides` で読み込む |

設定解決は `scripts/config.py` で行う。Python 3.10以上、標準ライブラリのみ。
`--project` を省略すると現在のGit作業ツリーのルート、Git外なら現在のディレクトリを使う。
設定の場所を曖昧にしないため、mainは通常プロジェクトルートを明示する。

```bash
python3 /path/to/hybrid-conductor/skills/conduct/scripts/config.py \
  --project /path/to/project \
  --overrides /path/to/run-overrides.json
```

出力は `config` と読み込んだ `sources` のJSON。辞書はキー単位で深くマージし、その他の値は置換する。
必要なキーだけ上書きできる。ファイルを書き換えたり、agentを起動したりするスクリプトではない。
明示された上書きファイルの欠落、無効なJSON、重複キー、不明キーはエラー。
各層を検証するため、壊れた下位設定を上位設定で覆い隠さない。

## 既定の役割

| 役割 | CLI | モデル | effort |
|---|---|---|---|
| main | そのまま | そのまま | そのまま |
| planner | Codex | `gpt-6-astra` | high |
| worker | Codex | `gpt-6-luna` | max |
| researcher | Codex | `gpt-6-luna` | max |
| reviewer | Codex | `gpt-6.1-sol` | high |
| designer | Claude Code | `claude-opus-5-5` | CLI既定 |

モデル名は任意の空でない文字列に変更できる。各CLIやアカウントでの利用可否は実行時に確認する。
API上のモデルIDを既定に用いるが、そのIDやeffortが導入済みCLIで使えることを保証するものではない。
Fableへplannerを変えるなど、CLIとモデルを同時に変更してよい。
main以外のmodelに `inherit` は使わない。高価なmainのモデルが意図せず継承されることを避ける。

`agent` はcodex / claude（mainのみinheritも可）。herdrのkind識別子そのものとは区別する。
`effort` はinherit / none / minimal / low / medium / high / xhigh / max。
この集合は設定構文としての許容値で、すべてのモデルで使えるという意味ではない。
`inherit` はそのCLI・モデル側の設定を利用する。指定値が実効値かどうかを導入版で確認する。

mainを明示指定してもこのスクリプトは現在のセッションを変更しない。
mainは要求を提示し、host側の正式なモデル切り替えが必要ならユーザーに伝える。
設定値だけから「実際にそのモデルで実行された」と報告しない。

## 小さな上書き例

```json
{
  "roles": {
    "planner": {"agent": "claude", "model": "fable", "effort": "high"},
    "reviewer": {"effort": "max"}
  },
  "parallelism": {"workers": 6, "researchers": 12}
}
```

既定の並列目安はworker 4、researcher 8。これは役割ごとの同時実行枠で、必ず全枠を起動する指示ではない。
mainが資源・レート制限・paneの可読性に応じて減らせる。補助スクリプトが枠を強制するわけではない。
追加reviewerやplannerを常駐させる枠ではなく、必要な時点で起動する。

`execution.adapter` はherdrのみ。`execution.allow_worktrees` は既定false。
trueはユーザーが確認した設定でworktree作成を許可する選択。許可されても必要な場合だけ作る。
今回の会話で作業場所を明示されたときは、その指定も適用する。

レビュー回数の設定項目はない。合格まで継続する方針は [レビュー方針](review.md) に置く。
秘密情報はこの設定へ保存せず、既存のCLI認証を使う。
プロジェクト由来の設定は、プロバイダーへの送信・権限の承認を代替しない。
