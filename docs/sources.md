# 参照した公式仕様と確認範囲

確認日: 2026-10-05。下記はWebで参照した一次資料。導入済みherdrの出力を取得した記録ではない。
実行環境の操作仕様は必ず `herdr --skill` で取得する。Webの最新版がローカル版と同じとは扱わない。

## herdr

- [Agent skill file](https://herdr.dev/docs/agent-skill/): `herdr --skill` でバイナリに対応するskillを取得できること、herdr内から操作すること。
- [公式skillのソース](https://github.com/herdrdev/herdr/blob/master/skills/herdr/SKILL.md): 設計時の照合用。識別子、状態、起動、待機、既定の作業場所、出力回収、再送時の注意を確認。
- [Agent automation](https://herdr.dev/docs/agent-automation/): 操作対象とagentライフサイクルの確認用。

公式skillはこのPluginへ複製していない。操作コマンドの全文を固定せず、読み込み手順と委任上の接続方針だけを持つ。
作成環境での直接実行は `herdr: command not found`。公式配布物のローカル取得もネットワーク制約で失敗した。
したがって、CLI版・server版・実機での出力は未確認。

## Claude Code

- [Create a plugin](https://code.claude.com/docs/en/plugins/create): `.claude-plugin/plugin.json`、`skills/`、`--plugin-dir`、名前空間付き呼び出し、公式validateコマンド。
- [Manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference): 最小manifestと標準配置。
- [Model configuration](https://code.claude.com/docs/en/model-config): `claude-opus-5-5`、Fableの選択、effortと実効設定が一致しない可能性。

このパッケージにClaude Code自身のバイナリは含めない。公式validateコマンドとモデル起動はこの環境では未実行。

## Codex / OpenAI

- [Build skills](https://developers.openai.com/codex/skills/): SKILL.md、`.agents/skills`、symlinkを用いたローカルskillの発見。
- [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra): planner既定のAPIモデルID。
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna): worker/researcher既定のAPIモデルIDとmax effort。
- [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol): reviewer既定のAPIモデルID。

APIの仕様確認は、各ユーザーのCodex CLIから同じ設定で起動できることの検証ではない。
Codexにはローカルskillとして登録する形を同梱し、Codex用Pluginディレクトリへの公開・配布は行っていない。

## このPlugin自身の設計判断

役割分担、checkpoint単位の独立レビュー、上限なしの修正ループ、既定の並列枠はユーザーとの合意に基づく。
それらがベンダーによって最適と保証された値や運用方法であるとは主張しない。
モックテストは安全確認と補助処理の検証であり、モデルの収束性や出力品質のベンチマークではない。
