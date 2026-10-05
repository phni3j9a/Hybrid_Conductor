# Hybrid Conductor

**強いplanner、安価な並列worker、成果単位の独立レビュー。**

herdr上でCodexとClaude Codeを役割別に使い分ける、skill中心のPluginです。
新しいエージェント実行基盤やherdr本体の拡張ではありません。
Claude CodeにはPluginとして、Codexには同じ2つのskillをローカル登録して利用します。

v0.1.0はherdrの現在のローカルセッションに対応する初版です。
T3 Code、リモートmachine制御、常駐daemon、自動で全処理を走らせるランナーは含めません。
実際の委任はmainがskillを読み、herdrを操作して実行します。

> **検証範囲:** 構造・設定解決・安全な導入・bootstrapのモックテストを実施。
> この作成環境にはherdr / Codex / Claude Codeがないため、実機でのagent起動とレビュー運用は未検証です。
> `herdr --skill` は実行を試みましたが `command not found` でした。
> [検証記録](docs/validation.md) と [実機シナリオ](tests/scenarios.md) を参照してください。

## 方針

計画はAstra、実装・必要時の調査はLuna max、独立レビューはSol、デザインはClaude系を既定にします。
mainのモデルは変更しません。すべての役割のモデル・effortは設定で変更できます。

レビューはworkerのタスクごとではなく、機能として評価できるcheckpointで行います。
初回は実装に参加していないコンテキストで広く確認し、修正後は未解決指摘と変更の影響を中心に確認します。
**回数上限はありません。** 合格条件を安定させ、停滞時に調査・担当・検証・設計判断を変えることで収束を目指します。
新しい実害を無視せず、任意の改善提案で完成条件を動かし続けない方針です。

researcherは必要時だけ起動します。designerはモック作成と実装後の視覚・操作確認を担当します。
小さなタスクで全役割を強制起動しません。

## 使い始める

必要なもの: herdr内で起動したmain、使用するCodex / Claude CodeのCLIと認証。
補助スクリプトにはPython 3.10以上が必要です。外部Pythonパッケージは不要です。
記載のshellとsymlink導入例はmacOS / Linux / WSL向けです。

### リポジトリを取得

```bash
mkdir -p "$HOME/src"
git clone https://github.com/phni3j9a/Hybrid_Conductor.git "$HOME/src/Hybrid_Conductor"
```

以下はこの保存先を使う例です。別の場所へcloneした場合はPluginのパスを読み替えてください。

### Claude Code

取得したPluginを指定し、既にherdrで管理されているpane内の、作業対象プロジェクトから起動します。
パッケージのディレクトリを作業対象と取り違えないでください。

```bash
cd /path/to/your-project
claude --plugin-dir "$HOME/src/Hybrid_Conductor"
```

Claude Code内で次を実行します。

```text
/hybrid-conductor:conduct プロフィール編集機能を実装してください
```

mainは最初にherdr接続用skillを読み、`herdr --skill`を実行します。
導入版に対応する仕様を使うため、公式herdr skillの全文はこのパッケージに同梱していません。

### Codex

パッケージを移動しない場所に置いてから、対象プロジェクトのskillディレクトリへリンクします。

```bash
python3 "$HOME/src/Hybrid_Conductor/scripts/install_codex.py" \
  --target /path/to/your-project/.agents/skills
```

全プロジェクトで使う場合は `--target` を省略すると `~/.agents/skills` にリンクします。
同名の既存skillは上書きしません。既にこのパッケージへリンク済みなら何もしません。
パッケージを移動するとリンクが切れるため、その場合はリンク先を確認して更新してください。

herdr内でCodexを起動し、次のように指定します。

```text
$conduct プロフィール編集機能を実装してください
```

公式のherdr skillを別途インストールしていても、この接続用skillの名前は `herdr-adapter` なので区別できます。

## 設定

[既定値](skills/conduct/assets/defaults.json) を直接編集する必要はありません。
ユーザー設定は `~/.config/hybrid-conductor/config.json`（XDG対応）、
プロジェクト設定は対象ルートの `.hybrid-conductor.json` に、変更したい項目だけ書きます。

例: plannerをClaude系へ、reviewerのeffortをmaxへ変更する場合。

```json
{
  "roles": {
    "planner": {"agent": "claude", "model": "fable", "effort": "high"},
    "reviewer": {"effort": "max"}
  }
}
```

優先順位は、**今回の明示指定 > プロジェクト > ユーザー > 既定値**です。
モデルIDとeffortの利用可否は、導入済みCLI・アカウントで確認します。
未対応時の黙ったモデル変更やeffortの引き下げはしません。

設定だけを確認するには次を実行します。agentは起動しません。

```bash
python3 "$HOME/src/Hybrid_Conductor/skills/conduct/scripts/config.py" \
  --project /path/to/your-project
```

並列の既定枠はworker 4、researcher 8。目安として設定可能で、常時全枠を使う指示ではありません。
herdrの既定に合わせ、同じtab・作業場所を使い、無断でworktreeを増やしません。
worktreeを許可する場合は `execution.allow_worktrees: true` を明示します。
詳しくは [設定仕様](skills/conduct/references/configuration.md) を参照してください。

## 構成

```text
.claude-plugin/plugin.json       Claude Code用manifest
skills/conduct/                 共通の入口・方針・設定・ノートひな型
skills/herdr-adapter/            herdr --skillを読む接続層
scripts/install_codex.py         同じskillをCodexへ安全にリンク
examples/                       部分的な設定上書き例
tests/                          自動テストと実機シナリオ
docs/                           検証記録・参照した公式仕様
```

常駐するhooksやMCPサーバーはありません。長いCLAUDE.md / AGENTS.mdへの追記も要求しません。
全方針を毎回読み込ませず、役割や段階に応じて参照します。
設定や読み取り専用の役割指示は、それ自体がOSの権限制御やプロセス制御を提供するものではありません。

## 検証

パッケージのルートから実行します。

```bash
python3 -m unittest discover -s tests -v
```

Claude Codeがある環境では、さらに公式の形式検証を実行できます。

```bash
claude plugin validate "$HOME/src/Hybrid_Conductor"
```

herdr pane内では、読み取り専用のbootstrap確認もできます。

```bash
python3 "$HOME/src/Hybrid_Conductor/skills/herdr-adapter/scripts/bootstrap.py"
```

bootstrapは `herdr --skill` の出力と環境を確認するだけです。
成功してもserver接続、モデル提供状況、実際のオーケストレーションが検証済みになるわけではありません。

## 設計の参照先

[進行方針](skills/conduct/references/workflow.md) ·
[レビュー方針](skills/conduct/references/review.md) ·
[役割](skills/conduct/references/roles.md) ·
[herdr接続](skills/herdr-adapter/SKILL.md) ·
[公式仕様と確認範囲](docs/sources.md)
