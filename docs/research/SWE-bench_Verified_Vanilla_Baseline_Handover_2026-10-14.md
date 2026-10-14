# SWE-bench Verified — Vanilla Baseline 実験記録・引き継ぎレポート

**記録日:** 2026-10-14（JST）  
**対象:** GPT-5.6 Terra / Medium を用いた SWE-bench Verified 全500問のパッチ生成と部分評価  
**実験ステータス:** **パッチ生成完了（500/500）／Docker評価進行中（370/500）／評価再開はユーザー判断待ち**  
**GitHub（非公開リポジトリ）:** `https://github.com/1716964609/swebench-baseline-results`  
**直近の成果物保存コミット:** `84f3721` — `Complete SWE-bench Verified baseline patch generation 500/500`  
**本書の性格:** 会話で共有されたターミナル出力・評価ログ・監査結果に基づくスナップショット。現時点でGitHub上の実ファイルを再読して独立に再集計した監査報告ではない。

---

## 1. Executive Summary

| 指標 | 現在値 | 判定 |
|---|---:|---|
| SWE-bench Verified 総問題数 | 500 | 固定 |
| パッチ生成完了 | **500/500（100%）** | **完了** |
| 最終70問（#431–500） | **70/70 predictions、70/70 non-empty patches** | 完了 |
| Docker評価完了 | **370/500（74%）** | 一部完了 |
| 評価済み Resolved | **269/370（72.70%）** | 暫定スコア |
| 未評価パッチ | **130問（#371–500）** | **保留** |
| Token Usage を監査済み | **360問（#11–370）** | 一部集計 |
| 生成Wall Timeを監査済み | **360問（#11–370）** | 一部集計 |
| AWS評価用環境 | **Terraform destroy 済み／EC2 terminated確認** | 課金停止のため破棄 |
| GitHubへの500問生成成果物の保存 | **Pushとremote SHA照合が成功** | 完了 |

**最も重要な区別:** `500/500` は**非空パッチの生成達成**であって、`500/500` の評価完了でも、100%解決率でもない。最終解決率は残り130問をDockerで採点して初めて確定する。

## 2. 実験目的と比較上の位置づけ

目的は、独自AIVP/ANSE機構を加えない **Vanilla Codex CLI** を比較基準として固定し、同一問題に対する将来のHarness/Hook/Reviewer実験と比較できるデータを残すこと。

- 各SWE-bench Issueを独立したタスクとして扱い、新しいCodex実行を開始。
- タスクごとに**最終パッチ、Codexイベント、実行ステータス、生成所要時間**を可能な限り記録。
- Dockerを使うSWE-bench評価は**パッチ生成とは別工程**で実施。
- 「10並列」は**独立した10タスクを同時処理**する意味。1問について10エージェントの共同推論を行ったという意味ではない。
- 今回のVanilla Baselineには、追加のClaude Reviewer、独自のSpec/長期Context管理、追加のAIVP Harness Panelは適用しない。Codex CLI自体に内蔵された探索・ツール利用・反復処理は含む。

## 3. 実験環境

### 3.1 パッチ生成（ローカル）

| 項目 | 設定・観測 |
|---|---|
| 端末 | MacBook Air M5、24 GiB RAM、1 TB SSD |
| 実行環境 | macOS、Python virtualenv（`~/swebench-play/.venv`） |
| Agent | Codex CLI `0.162.1` |
| モデル設定 | `gpt-5.6-terra`（Runner中の実験ラベル） |
| Reasoning effort | `medium` |
| 同時実行数 | `MAX_WORKERS = 10`（後半のRunner） |
| 1問のTimeout | `TIMEOUT = 1800` 秒（後半のRunner） |
| 生成ファイル | `tasks.json`, `predictions.jsonl`, `batch.log`, `status/*.json`, `logs/*.events.jsonl`, `logs/*.stderr.log`, `patches/` など |
| Codex実行の利用体系 | ChatGPTプランによるCodex利用枠。APIとしての実請求額は測定していない |

後半Runnerの設定は実行時出力で確認。初期バッチではRunnerの構造・ログ形式が異なるため、**すべてのバッチが完全に同一の実装・計測仕様だったと断定しない**。

### 3.2 Dockerによる評価（AWS、現在破棄済み）

| 項目 | 設定・観測 |
|---|---|
| AWSリージョン | `ap-northeast-1`（東京） |
| AWS profile | `tvp-terraform` |
| インスタンス | Spot `m7i.8xlarge`（32 vCPU / 128 GiB RAM） |
| EBS | 暗号化gp3、600 GiB（終了時削除設定） |
| OS | Ubuntu 24.04、amd64 |
| 評価ツール | SWE-bench CLI `5.0.2` |
| 参照タスクrepo HEAD | `3d07b464b7b311a0cbfb5ed5b2d8a3b96f84a33d`（既存環境の固定値） |
| 並列評価 | `-j 12` |
| AWS EC2 ID | `i-0733b2ba89c71702f`（**terminated確認済み**） |
| インフラ管理 | `~/swebench-aws-eval` のTerraformローカルState |
| 処理中の注意 | Ubuntuの`docker.io`だけではBuildxが不足し、`docker-buildx`の追加導入が必要だった |

**2026-10-13〜14に実施した後片付け:** `terraform apply swebench-destroy.tfplan` により**11リソース削除**。`terraform state list` は空、`aws ec2 describe-instances` は対象インスタンスを `terminated` と表示。**現時点で評価用EC2は稼働していない。** 次回評価には新たな構築と費用確認が必要。

## 4. Docker評価のバッチ別結果

| 問題範囲 | 評価数 | Resolved | 解決率 | 状況・注記 |
|---|---:|---:|---:|---|
| #1–100 | 100 | 66 | 66.0% | Mac側で先行評価。元の全レポートの保存先は要再監査 |
| #101–120 | 20 | 14 | 70.0% | Ambiguous Failure 3件、Infra Failure 0件 |
| #121–150 | 30 | 23 | 76.7% | Ambiguous Failure 1件、Infra Failure 0件 |
| #151–170 | 20 | 15 | 75.0% | AWS評価完了 |
| #171–200 | 30 | 25 | 83.3% | AWS評価完了 |
| #201–230 | 30 | 21 | 70.0% | AWS評価完了 |
| #231–260 | 30 | 22 | 73.3% | AWS評価完了 |
| #261–320 | 60 | 44 | 73.3% | AWS評価完了（約22分26秒） |
| #321–370 | 50 | 39 | 78.0% | AWS評価完了（約13分53秒） |
| **評価済み小計** | **370** | **269** | **72.70%** | **暫定結果** |
| #371–430 | 60 | — | — | **パッチ生成のみ、未評価** |
| #431–500 | 70 | — | — | **パッチ生成のみ、未評価** |
| **全体** | **500** | **未確定** | **未確定** | **130問の評価待ち** |

注: AWSで評価した#101–370の270問には、報告されたAmbiguous Failureが計4件あった。これはResolvedではない。#1–100の失敗分類の完全な内訳は本書では確定しない。評価ログに表示された`Total instances 2294`などは評価対象数500や当該バッチの提出件数を表すものではない。

## 5. Token Usage監査（#11–370、360問）

ローカル `batch_*/logs/*.events.jsonl` から`turn.completed.usage`を抽出。監査時には対象ファイル**360件**、UsageのあるTrace**360件**、`turn.completed` **360件**、`turn.failed` **0件**、`error`イベント**1件**を確認。

| 指標 | 360問の合計 | 1問平均（参考） |
|---|---:|---:|
| Input tokens | **106,353,822** | 約295,427 |
| Cached input tokens | **96,524,800** | 約268,124 |
| Uncached input tokens | **9,829,022** | 約27,303 |
| Output tokens | **1,098,490** | 約3,051 |
| **Input + Output** | **107,452,312** | 約298,479 |
| Cached / total input | **90.76%** | — |

`cached_input_tokens`は`input_tokens`の内数であり、二重計上しない。Inputの延べトークン数は、複数ターンのモデル呼び出しで再提示された文脈を含むため、単一Prompt長ではない。**これは#11–370の360問の値であって500問の総計ではない**。

API単価換算を行う場合の理論式（各`P`は100万トークンあたり単価）:

```
Estimated API-equivalent cost =
  9,829,022 * P_uncached_input / 1,000,000
+ 96,524,800 * P_cached_input / 1,000,000
+  1,098,490 * P_output / 1,000,000
```

実際のCodex/ChatGPT課金額とは異なる。価格表・モデルの実際の課金区分を確認するまでは金額として確定しない。

## 6. 生成Wall Time監査（#11–370、360問）

初回集計では#11–40の`batch.log`の書式が他のバッチと異なり、330問しか検出できなかった。その後、`batch_11_40/status/*.json`内の`elapsed_seconds`（Runnerで`time.monotonic()`により測定）を確認し、**30問分の時間を回収**。最終的に#11–370の**360/360問**が揃った。

| 指標 | 結果 |
|---|---:|
| 対象数 | **360問** |
| Mean | **129.25秒** |
| Median | **103.03秒** |
| Minimum | 25.21秒 |
| P75 | 164.90秒 |
| P90 | 246.33秒 |
| P95 | **300.88秒** |
| P99 | 425.81秒 |
| Maximum | 696.86秒 |
| 合計Task Wall Time | **46,528.6秒（12.92時間）** |

**12.92時間はタスクごとの時間の合計であり、Mac上で経過した実時間ではない。** タスクは最大10並列で進行。各分位点は当時の監査スクリプトの抽出・算定方式に基づく。

なお、#371–500でも`status/`やTraceは生成されているが、この会話の時点では**130問分のToken/Wall Timeの統合集計をまだ実施していない**。最終的な全500問の平均値を推測で記載しない。

## 7. パッチ生成の最終到達点

### Round 11 — #371–430

- 60問を10並列で自動実行。
- macOS `nohup` + `caffeinate -is` + Shell待機を使用し、**2026-10-14 01:40 JSTの自動起動を予約**。
- **01:54:30 JSTに正常終了**。`Predictions: 60/60`、`Non-empty patches: 60`。
- 自動実行はユーザーの直接介入なしで完了。これは**実行スケジューリングの成功**を示すものであり、パッチの解決率とは別。

### Final Round — #431–500

- 70問を10並列で処理。
- `Predictions: 70/70`、`Non-empty patches: 70`。
- 実行コマンドの総経過時間：約**13分42秒**。
- 当該70問のログ上の対象リポジトリはすべてDjango（`Repositories: 1`）。**問題の処理順と難易度・リポジトリ構成の偏りを考慮すること**。全500問の平均値には完了後の全件集計を使う。

### バックアップ

`~/swebench-results` のローカルCheckoutから以下の成果物をGitHubにPush:

- `batch_371_430/{run.py,tasks.json,predictions.jsonl,batch.log,SHA256SUMS.txt,status/}`
- `batch_431_500/{run.py,tasks.json,predictions.jsonl,batch.log,SHA256SUMS.txt,status/}`

最終Pushは `6c6fd30..84f3721 main -> main` と表示され、ローカルHEADと`ls-remote`の一致検証は成功。**詳細Codex Trace (`logs/*.events.jsonl`等) は、従来どおりMacのローカル環境を保全先とする**。GitHubのログ・パッチだけで完全なToken監査を再現できるとは限らない。

## 8. 成果物・ファイル配置

| 場所 | 役割 |
|---|---|
| `~/swebench-play/` | ローカル実験Workspace、バッチRunner、Codex Trace |
| `~/swebench-play/batch_371_430/` | Round 11の60問と各種ログ |
| `~/swebench-play/batch_431_500/` | Final Roundの70問と各種ログ |
| `~/swebench-results/` | GitHub Private RepoのMac側Checkout |
| `~/swebench-results/evaluation/aws-baseline-*/` | AWS各バッチの`report.json`、`predictions.jsonl`、`evaluation.log`、SHA256 |
| `~/swebench-aws-eval/` | 再構築可能な評価用Terraform（現時点State空） |
| GitHub `main`@`84f3721` | 500問パッチ生成完了時点の保存済み参照点 |

AWSの評価レポートは`evaluation/aws-baseline-101-120`、`121-150`、`151-170`、`171-200`、`201-230`、`231-260`、`261-320`、`321-370` の各ディレクトリがGitHub経由でMacへ同期済みであることを確認。**先行#1–100の公式評価レポートのバックアップ完全性は再確認事項**。

## 9. データ品質・解釈上の制約

1. **Patch生成成功 != Issue解決成功。** 解決率は採点済み370問についてのみ報告。
2. **Token/時間監査の対象は360問。** #1–10のTrace/Timingは未確認、#371–500は未統合集計。欠損・未集計を0とみなさない。
3. **Recovery Capabilityは未測定。** `turn.failed=0`は失敗からの回復能力が100%であることを意味しない。専用Fault Injectionや状態遷移の計測が必要。
4. **Harness Overheadは未測定。** Vanillaを比較基準とし、今後同一タスク・同一機材条件で追加機構の差分を評価する。
5. **実支出は未集計。** Token計数は推論資源指標であり、月額プランの実請求額・AWS請求額とは異なる。
6. **モデル名は当時のRunner設定ラベル。** サービス側のモデル実体・バージョン固定が保証されたとは記載しない。
7. **初期バッチと後半バッチでRunner形式が異なる。** 追加実験では条件差（Codex CLIのバージョン、Prompt、Timeout、Worker数等）を監査する。
8. **評価器の実装・タスクRepoのコミット・予測JSONLの整合性を保持すること。** SWE-bench Verifiedの評価は、指定のデータセット・イメージ・判定実装に依存する。
9. **代表性・情報漏洩の評価は別問題。** SWE-benchタスクは公開されており、モデル学習データとの重複可能性を本実験だけでは否定できない。公式Leaderboardのスコアとして表現しない。

## 10. 再開時の作業（実行時刻は未決定）

**この文書作成時点では、次の評価の実行日時はユーザーから指定されていない。AWSの再構築・Docker評価を自動で開始しない。**

実行が決まった際の手順は以下のとおり。

1. **生成成果物とGitHubの保存状態を確認**（`main`、コミット、500件の`instance_id`のユニーク性、Patch非空、各バッチのSHA256）。
2. **#1–100の元評価レポートの保存場所・整合性を再監査。** 500問の総合評価レポートに欠落が残らないようにする。
3. **AWS Spot/EC2の時価・EBS・利用時間を確認し、費用上限を決める。** TerraformのDestroy対象がSWE-bench専用環境のみであることを確認。
4. **Terraformで一時評価環境を新規作成。** `docker-buildx`、Docker daemon、Python/venv、SWE-bench CLI、タスクrepoの固定HEAD、12並列などをセットアップ。
5. **#371–430（60件）と#431–500（70件）を評価。** 既存の`predictions.jsonl`を統合/整形し、提出件数・IDを事前検証。Docker評価はタスク群を分けて実行し、各評価結果を保存。
6. **GitHubへ評価レポート・使用予測JSONL・実行ログ・SHA256をバックアップし、Remote Commitまで検証。** その後Macへ同期。
7. **EC2と付随ストレージをTerraform Destroyで削除。** `terminated`とTerraform State空を確認（その他のAWS環境は触らない）。
8. **全500問のResolved Rate確定。** `resolved_ids`の重複・未提出・Ambiguous/Infra件数を監査。問題単位の比較表を生成。
9. **#371–500のToken/Wall Timeを追加集計。** `status/*.json`と`events.jsonl`からPer-Issue Datasetを作り、欠損理由も記録。

参考: 前回のAWS上の代表的評価コマンド形式（**再実行時には入力ファイルとrun-idを必ず変更する**）:

```bash
cd ~/swebench-play
source .venv/bin/activate
set -o pipefail
swebench eval verified \
  -p aws-eval/predictions_321_370.jsonl \
  --run-id aws-baseline-321-370 \
  --task-repo ./swe-bench-tasks \
  -j 12
```

これは**過去に実施したコマンドの記録**であり、残り130問に対してそのまま実行する指示ではない。

## 11. 現時点の研究判断・次フェーズ

- SWE-bench Verifiedは**独立したIssue単位の修正能力**を比較する目的に適している。
- 次の候補は **Vanilla vs 決定論的Hooks vs AIVP v2（Codex Generator + Claude Reviewer + 決定論的検証・制御）**。AIVP v2に独立したLLM Fixer/Verifierは存在しない。
- **長期的Context Engineering、Spec-Driven Engineeringの効果**は、複数の機能追加・仕様変更が積み重なる継続開発環境で別に検証する方針を検討。SWE-bench単発Issueで無理にANSE全体を採点しない。
- 上記は今後の**研究候補**であって、実装済み・評価済みという意味ではない。

---

## 12. 次の会話に渡す短い引き継ぎ文

> 2026-10-14 JST時点、SWE-bench Verified 500件についてGPT-5.6 Terra/medium・Codex CLI `0.162.1`によるVanilla Baselineパッチ生成が500/500件完了（全件非空）。GitHub Private Repo `1716964609/swebench-baseline-results` の `main`@`84f3721`へ保存・Remote Commit一致確認済み。Docker評価は370/500件まで完了、269/370 Resolved（72.70%）、残り#371–500の130件は未評価。#11–370の360件に対するToken Usageは Input 106,353,822（内Cached 96,524,800）、Output 1,098,490、合計107,452,312。生成Wall Timeは平均129.25秒、中央値103.03秒、P95 300.88秒、合計46,528.6 task-seconds。AWS東京の評価用Spot `m7i.8xlarge`と600GiB EBSはTerraformで削除済み、EC2はterminated。**ユーザーの指示があるまでAWS再構築・残り130件の評価を開始しない。** 次は残130件の予測JSONLを検証し、再構築したAWS評価基盤で2バッチを評価、レポートをGitHubへ保管し、全500件の最終スコアとPer-Issue Token/時間統合表を確定する。

**End of handover snapshot.**
