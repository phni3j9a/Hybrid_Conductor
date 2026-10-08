# タスク単位のセッションと復帰

Mainが `.hybrid-conductor/runs/<run-id>/checkpoint.md` を進捗の正本として保持する。
実行基盤の履歴は会話継続の補助。Checkpointが失われてもよい理由にはしない。

## 初回と継続

| 役割 | 初回 | 同じ仕事の続き |
|---|---|---|
| Planner | Fresh | Resume |
| Worker | Fresh | Resume |
| Reviewer | Fresh・実装者から独立 | Resume |
| Researcher | Fresh | 原則Fresh。未完の同じ調査はResume可 |
| Designer | Fresh | Resume |

Freshのhandoffに目的・担当範囲・合意条件・参照先・検証方法・返却内容を含める。
ReviewerにはWorkerの会話を渡さず、対象コード・仕様・対象版・検証証跡を渡す。
Project規約は保持。PiのGlobal指示・無関係なSkill・Agent永続memoryは既定で継承しない。

## Checkpointへ記録する情報

- タスクID、役割、状態、依存先、担当パス、作業場所、受け入れ条件とその版
- 実行基盤、Agent名、要求/実効モデルとthinking、run ID、最新のResume先と履歴の参照先
- 対象commit、未commit/未追跡変更の識別情報、検証コマンド・結果と対象版
- 指摘ID、未解決条件、修正内容、独立確認結果、次の対応

初回実行のIDを固定せず、Resumeの新しい応答ごとに最新IDへ更新する。
処理途中にも記録する。AgentにCheckpointなどの管理ファイル作成を要求しない。
報告の返し方は [進行方針](workflow.md) の「報告の受け渡し」に従う。

## 圧縮・再起動からの復帰

1. Checkpointを読み、現在の作業ツリーとレビュー対象版を照合する。
2. 記録した最新IDを実行基盤に照会する。まだ稼働中なら接続/結果回収を優先する。
   timeoutや取得失敗だけを未実行の証拠にしない。書き込み中か不明なら重複writerを起動しない。
3. 再開可能な同じ役割セッションをResumeする。Piではstatusは参考、resumeが最終的な可否判断。
   子一覧の件数や親セッションscopeに依存せず、記録したIDを使う。
4. セッション消失・再開不可なら理由を記録し、CheckpointからFreshで引き継ぐ。
   仕様変更・モデル/権限変更・古い会話の肥大化でもFreshへ切り替えてよい。
5. 未解決指摘と受け入れ条件を維持し、再実装やレビュー省略で復帰を代用しない。

タスク終了時は成果を回収して最終状態とIDを記録する。別タスクはFreshで開始する。
herdrの自分が作成したpane/agentは成果回収後に導入版手順で片付けてよい。
Piの完了セッションは保存状態のまま残し、独自常駐を作らず、保存履歴を自動削除しない。
共有ディレクトリでは同じファイルを編集するwriterを直列化する。worktreeは明示許可時のみ。
