# 起動の準備とテンプレート

agentを起動する直前に読む。herdrの操作構文は複製しない。**導入版の `herdr --skill` とhelpが常に優先。**
以下は確認したバージョンでの既定例で、CLIの更新で変わり得る。起動後は必ず実効値を確認する。

確認環境（2026-10-05）: herdr 0.9.3（server 0.9.1）、codex-cli 0.160.0、Claude Code 2.1.289、Linux / zsh。

## paneの準備と名前

1. 導入版skillの手順でsibling paneを作り、応答から新しいpane IDを読む。
2. **paneを作った直後にshellのプロンプトを待つ。** rcの対話確認（例: oh-my-zshの更新確認）が出ていると、
   `agent start` の起動コマンドが入力として食われる。startがtimeoutしたら `pane read` で画面を確認し、
   確認には勝手に答えず、プロンプトに戻るのを待つかユーザーへ確認してから起動し直す。
3. **paneとagentに同じ役割名を付ける。** 名前は `hc-<role>` または `hc-<role>-<担当>`（例: `hc-planner`、
   `hc-worker-core`、`hc-reviewer`）。agent名の制約 `[a-z][a-z0-9_-]{0,31}` に収め、生存中のagentで一意にする。
   paneのラベルは導入版の `pane rename` で付ける。agent名はagentの終了で消えるが、paneのラベルは残る。
4. 終了したagentのpaneを別の役割に再利用するときは、起動前にラベルを付け替える。
   役割の終わったpaneは閉じるか、ラベルを外す。自分が作っていないpaneのラベルは変更しない。

並行する別のrunと名前が衝突するなら、runの短い識別子を足す（例: `hc-a1-worker-core`）。

## 役割と権限

| 役割 | 書き込み | 理由 |
|---|---|---|
| worker / designer | workspace-write | 担当範囲の実装・モック作成 |
| planner / researcher / reviewer | read-only | 計画・調査・判定を返すだけ。成果物はmainが記録する |

承認なし（`never` / bypass）で起動してよいのは、ユーザーまたは既存の環境設定がそれを許可している場合だけ。
許可がなければCLIの既定の承認方式で起動し、blockedになった承認・質問はユーザーへ確認する。
読み取り専用でも実験が必要な役割は、mainと合意した隔離場所だけに書き込み権限を広げる。

## Codex

```bash
# 書き込み可能な役割
codex -m "<model>" -c 'model_reasoning_effort="<effort>"' \
  -c 'default_permissions=":workspace-write"' -s workspace-write -a never
# 読み取り専用の役割
codex -m "<model>" -c 'model_reasoning_effort="<effort>"' \
  -c 'default_permissions=":read-only"' -s read-only -a never
```

- **`config.toml` に `default_permissions` があると `-s` が無視される。** 実測では `-s read-only` だけで起動した
  agentが `danger-full-access` で動き、ファイルを書き込めた。必ず `-c default_permissions=...` も併せて渡す。
- `-c` を渡すと、共有のbackground serverを使わないembedded modeになったという警告が出る。動作上の問題はない。
- `-a never` は上記の許可がある場合だけ付ける。
- 未信頼のフォルダでは「Trust this folder?」の確認でstartがblockedになり、`-c projects."<path>".trust_level=...`
  では回避できなかった。信頼を選ぶとユーザーの `~/.codex/config.toml` に恒久的に記録される。
  勝手に選ばずユーザーに確認する。使い捨ての検証環境で信頼した場合は、終了時にその記録を戻す。

起動後に `/status` を送り、`Model:` のモデル・reasoningと `Permissions:` を読む。
例: `Model: GPT-6-Astra (reasoning high, ...)`、`Permissions: Workspace (never)`。ずれていれば作業を渡さない。

## Claude Code

```bash
claude --model "<model>" --effort "<effort>" --permission-mode "<mode>" -n "<役割名>"
```

- 書き込み可能な役割は許可の範囲で `acceptEdits` などを、読み取り専用の役割は `plan` を使う。
- `effort` が `inherit` なら `--effort` を渡さない。
- 起動後の画面や `/status` でモデルと権限モードを確認する。子として起動するClaude Codeのテンプレートは、
  2026-10-05時点では実機で未検証。

## 終了

役割が終わったagentは導入版の方法で終了させる。自分が作ったpaneだけを閉じる。
`/quit` などの終了操作の後は、shellのプロンプトに戻ったことを確かめてからpaneを再利用する。
