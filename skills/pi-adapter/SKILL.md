---
name: pi-adapter
description: "Hybrid ConductorをPi Mainとpi-subagentsで実行する。Pi専用Agent、nativeモデル設定、Fresh/ResumeとCheckpoint復帰を使うときに読む。herdrの操作や独自実行エンジンの代替には使わない。"
---
# Hybrid Conductor: Pi adapter

Pi自身がMain。pi-subagentsが子実行を管理し、[conduct](../conduct/SKILL.md) が共通方針を提供する。
独自Extension、Durable、常駐デーモンは不要。herdr向けモデル設定でPiの子を起動しない。

## 接続と設定

1. `subagent` がなければ導入不足を示す。利用可能な `subagents_enable` でツールを有効化してよい。
   導入版の `subagent({action:"guide", topic:"agents"})` と `topic:"tool-reference"` を読み、
   `subagent({action:"list"})` で `hybrid-conductor.<role>` 全5種類を確認する。
   例の構文が導入版と異なる場合は導入版に従い、対応していない機能を実行可能と装わない。
2. [モデル設定](../conduct/references/model-setup.md) に従い、
   `python3 <conduct>/scripts/config.py --project <ルート> --adapter pi --check-setup` を実行する。
   標準以外の設定場所やプロジェクトroot解決の場合は、実際のnative保存先を
   `--pi-user-settings` / `--pi-project-settings` で渡す。指定ファイルは存在必須。
   `subagents.defaultModel` や親モデルだけでは設定完了としない。
3. 未設定なら `subagent({action:"models"})` の正確な `provider/id` と推奨候補を提示し、
   全5役割を確認してnative `subagents.agentOverrides` に保存する。無関係な設定を保持する。
   Userは `~/.pi/agent/settings.json`、Projectは `.pi/settings.json`。Projectが優先。
   設定後は導入版に従って再読込し、list/modelsで実効Agent・モデル・thinking・toolsを再確認する。
4. `model` は全役割必須。thinking未指定はPi・モデルの既定。`inherit` はモデルに使わない。
   実行時の明示変更は正規の `model:"provider/id:level"` で渡す。
   未対応effortを自動変換しない。設定やoverrideで独立性・権限が変わっていたら起動前に解決する。

## 委任と回収

初回は `subagent({agent:"hybrid-conductor.worker", task:"<handoff>", context:"fresh", cwd:"<root>"})`。
Handoffは目的、タスクID、担当パス、受け入れ条件、参照先、検証方法、返却内容を含める。
Mainの全履歴やWorkerの会話をReviewerへ渡さない。子には必要な役割方針だけを渡す。
全AgentはProject指示を継承、Global指示・Skillカタログは継承しない。永続role memoryは有効化しない。

独立タスクを導入版のasync/parallel方式で起動し、状態と成果を対応するrun IDで回収する。
共有ディレクトリでは担当パスを分け、同じファイル・lockfile・生成物の編集を直列化する。
worktreeは `execution.allow_worktrees:true` または今回の明示許可時だけ使用する。
レビュー中は対象への書き込みを止め、commitと未追跡ファイルを含む内容を固定する。
Reviewerは `read, grep, find, ls` のみ。必要なテストはMain/Workerが実行し、対象版と証跡を渡す。
ツール制限と役割指示はOS sandboxではない。実効allowlistと拡張の有無も確認する。

## 継続と修正

[セッション手順](../conduct/references/sessions.md) と [レビュー方針](../conduct/references/review.md) に従う。
同じ仕事のWorker/Reviewer/Planner/DesignerはResume、独立Researcherは原則Fresh。
`subagent({action:"status", id:"<最新run-id>"})` で対象を確認し、
`subagent({action:"resume", id:"<最新run-id>", message:"<続き・指摘ID・対象版>"})` を使う。
Resume receiptは完了ではない。導入版の待機/結果取得で新しいrun IDと成果を回収し、Checkpointを更新する。
元のAgent・モデル・toolsが望む条件と合わない場合は新しいFresh実行で引き継ぐ。
workflowの反復・復帰上限にレビューを閉じ込めない。MainがPASSまで子実行を追加する。

失敗・タイムアウト後は送信済みか、書き込み中かを確認してから再試行する。
再起動後のID照会・Resumeが失敗したらCheckpointからFresh復帰する。未回収実行を重複起動しない。
タスク終了後は完了結果と最新IDを記録し、別タスクで履歴を使い回さない。
無関係なセッション停止や保存済み子履歴の削除を行わない。
