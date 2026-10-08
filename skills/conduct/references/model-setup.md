# 初回モデル設定（Pi / herdr共通）

起動時にplanner / worker / reviewer / researcher / designer全5役割の明示モデル設定を確認する。
Mainは現在のモデルのまま。defaultsは候補であり、設定完了の証拠にしない。

| 役割 | 推奨候補 | Thinking / effort |
|---|---|---|
| planner | GPT-6 Astra (`gpt-6-astra`) | high |
| worker | GPT-6 Luna (`gpt-6-luna`) | max |
| reviewer | GPT-6.1 Sol (`gpt-6.1-sol`) | high |
| researcher | GPT-6 Luna (`gpt-6-luna`) | max |
| designer | Claude Opus系 | モデル・CLI既定 |

推奨IDが導入済み環境で使えるとは限らない。Piではmodels一覧からprovider付きの正確なIDを選ぶ。
herdrではnative CLIのhelp/モデル設定を確認する。Designerの具体的なOpus版も利用可能な一覧で決める。
API・サブスク認証は各環境の既存方式を使用し、ここへ秘密情報を保存しない。

## 確認と保存

1. Adapterの導入版仕様を読み、`config.py --check-setup --adapter <pi|herdr> --project <root>` を実行する。
   終了コード0は明示指定が揃ったことだけを示す。モデル利用可否・実効設定は別途確認する。
   終了コード3はsetupが必要、2は設定エラー。通常の `config.py` 解決だけで委任しない。
2. 初回または設定不足なら全5役割の現在値・不足・推奨候補をまとめて提示する。
   既存の明示設定を保持しつつ、全役割をユーザーが確認・選択できるようにする。
   推奨を採用する旨の明示応答で一括設定してよい。無回答を承認としない。
3. herdrは既存ユーザーconfigの `roles` へ保存する。Piはnative `subagents.agentOverrides` へ保存する。
   保存先scopeを明示し、無関係なキーを残す。保存後に再チェックし、runtimeの実効値も確認する。
   今回の一時指定は起動時優先するが、永続保存の希望がなければ永続設定を無断変更しない。
4. 全役割の明示modelがある既存設定は設定済みとして移行でき、完了フラグを別途要求しない。
   thinkingは任意。herdrは従来のeffort解決、PiはPi側の既定を使用する。
5. 設定済みなら以後の対話確認を省略する。利用不可・無効化された役割だけ再設定する。
   他のモデルやMainの高価なモデルへ黙ってfallbackしない。未知の実効値はunknownと記録する。

Piのキーは `hybrid-conductor.planner` などnamespace込みで指定する。
以下は形の例であり、`provider/model-id` を実際のモデルIDへ置き換えて全役割を保存する。

```json
{
  "subagents": {
    "agentOverrides": {
      "hybrid-conductor.planner": {"model": "provider/model-id", "thinking": "high"},
      "hybrid-conductor.worker": {"model": "provider/model-id", "thinking": "max"},
      "hybrid-conductor.reviewer": {"model": "provider/model-id", "thinking": "high"},
      "hybrid-conductor.researcher": {"model": "provider/model-id", "thinking": "max"},
      "hybrid-conductor.designer": {"model": "provider/model-id"}
    }
  }
}
```

Skillの確認方針はエージェントへの指示であり、独自runtimeで強制する仕組みではない。
