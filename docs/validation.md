# 検証記録 — v0.2.0

実施日: 2026-10-08。Pi Main対応、共通初回モデル設定、Checkpoint復帰を追加。

| 検証 | 結果 |
|---|---|
| `python3 -m unittest discover -s tests -v` | 47件成功、失敗0、skip 0 |
| Pythonコンパイル / `git diff --check` | 成功 |
| herdr初回設定 | defaultsだけで未設定、全役割の既存明示設定で完了、部分設定・層別優先順位を検証 |
| Pi初回設定 | native namespace・全5役割・Project優先・thinking任意/false・無効設定・read-onlyを検証 |
| pi-subagents native parser | 全5Agentのnamespace、Fresh、context flags、空extensions、Reviewer allowlistを確認 |
| Skillとパッケージ | 3Skillのfrontmatter・相対リンク、Pi公開Skill/Agent pathsを検証 |
| Codex installer / herdr bootstrap | 既存の隔離fixtureテストが成功 |
| 認証済みPi/herdrでの委任・再開・レビュー | 未検証。実行CLI・認証環境なし |

ログ: [test-output.txt](test-output.txt)。native parserはnicobailon/pi-subagents
commit `0c33ec7cb26ed1db270d72e746c3c975be880aeb`（package版0.76.1）に対して確認。
これはPi上でのAgent discovery・モデル利用・セッション復帰の実機検証ではない。

```bash
node --experimental-strip-types tests/verify_pi_agents.mjs /path/to/pi-subagents
```

[実機シナリオ](../tests/scenarios.md) に従い、インストール済みバージョンで
Agent discovery、認証済みprovider、実効model/thinking/tools、Fresh/Resume、再起動復帰を確認する。
未対応のmaxや取得できないrun IDのfallbackも対象。herdr接続は導入版 `herdr --skill` が基準。

方針はSkillへの指示であり、強制runtimeやOS sandboxを追加したものではない。
