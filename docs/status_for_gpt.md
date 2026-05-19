# NavigationAnalyzer — Status Brief for GPT-pro

> **Ask:** I'd like development ideas for where this project should go next.
> 何を作るべきか、どの順番で投資すべきか、捨てるべき方向はないか、競合との差別化軸、刺さりそうな OSS ニッチなど、率直なアドバイスが欲しいです。

---

## 1. Vision (one line)

**ロボットナビゲーションのための「Datadog 風 観測 + 回帰評価 + AI 可読診断」を兼ねた CLI-first な OSS。**
ROS2 / Nav2 / Autoware の bag を入力に、メトリクス・失敗分類・診断を構造化 JSON / Markdown / Web UI として吐く。

- 主要利用者の想定: ナビゲーションのデバッグをする研究者・ロボットスタートアップのエンジニア・CI で回帰評価したい人・LLM エージェント。
- 競合的位置づけ: foxglove(可視化)、rosbag2 ツール群(録画/再生)、Autoware evaluator、Nav2 内蔵 evaluator のいずれも「観測 + 回帰 + AI 可読」を 1 つのアーティファクトに統合していない、という賭け。

---

## 2. アーキテクチャ概要

```
ROS2 bag / canonical JSON / unitree log
            │
            ▼
      NavigationRun (canonical schema, pydantic)
            │
   ┌────────┼─────────┐
   ▼        ▼         ▼
metrics  failures  diagnostics
   └────────┬─────────┘
            ▼
     AnalysisArtifact
            │
   ┌────────┼─────────────┐
   ▼        ▼             ▼
analysis.json  report.md  FastAPI
            │
            ▼
    React + Three.js + Plotly Web UI
```

- 設計原則: 「canonical schema が契約。reader/出力はそこから派生」。プラグイン抽象はまだ入れない (D005)。
- CLI コマンド: `analyze` / `convert` / `benchmark` / `report` / `serve`。
- バックエンド: Python (pydantic / typer / FastAPI)。フロントエンド: Vite + React + TS + Three.js + Plotly。
- リポジトリ規模: backend 約 1.6k 行 (analysis 系のみ)、フロントエンドは 4 コンポーネント。

---

## 3. 今動くもの (What works today)

### 入力 readers
- canonical JSON
- ROS2 bag (`rosbag2_py` 動的 import、Nav2 と Autoware の topic profile 両対応)
- `lanelet2_map.osm` 直接パース (Autoware 依存なし)
- unitree-nav-sim の `record_nav` ログ取り込み

### メトリクス (純関数 over `NavigationRun`)
- 共通: `success_rate` / `path_length` / `goal_distance` / `time_to_goal` / `collision_count` / `oscillation_count` / `recovery_count` / `path_smoothness` / `minimum_obstacle_distance`
- Goal フレーム: `final_lateral_error` / `final_longitudinal_error` / `final_yaw_error` / `final_stopped_duration`
- Autoware ルート: `route_progress_ratio` / `route_straight_line_lateral_error` / `route_straight_line_remaining_distance`
- Lanelet centerline: `route_lanelet_centerline_distance` (final/mean/max), `route_lanelet_progress_ratio`, `route_lanelet_remaining_distance`, `route_lanelet_matched_count`

### 失敗分類 (rule-based, deterministic)
`localization_drift` / `oscillation` / `deadlock` / `narrow_passage_failure` / `dynamic_obstacle_freeze` / `planner_divergence` (Autoware では route メタデータが evidence に追加)

### 診断 (非致命的 warning, 別タクソノミー)
`goal_reached_route_progress_mismatch` / `route_lanelet_deviation`
ベンチマーク gate にもオプションで参加可 (`max_count` / `max_level` / `disallow_types`)。

### ベンチマーク / CI gate
- 複数 run の比較 (baseline 差分、メトリクス deltas、failure / diagnostic counts)
- `config/benchmark_nav2.yaml` (Nav2 SimpleGoalChecker 流) と `config/benchmark_autoware.yaml` (到着判定流) のプロファイル
- `--fail-on-regression` で GitHub Actions の gate として使える (`.github/workflows/ci.yml` 設置済)

### Web UI
- ローカル `analysis.json` / `benchmark.json` をブラウザのファイルピッカーで開く
- Three.js: 軌跡再生・goal/start/finish マーカー・失敗ポイント・costmap
- Plotly: メトリクスプロファイル・障害物距離ヒートマップ
- マルチランダッシュボード (run cards / metric bars / failure counts / threshold violations / baseline diffs)
- Playwright で「キャンバスが真っ黒じゃない」回帰チェック

### Autoware エンドツーエンド
- 公式 docker (`universe-jazzy-1.8.0`) を解析用にも使う docker-in-docker 風ワークフロー (`docker/autoware-analyzer/Dockerfile`)
- planning_simulator を RViz なしで起動 → 初期姿勢 → ルート → autonomous mode → record → 解析、までスクリプト化
- 実機の sample-map run で `success=1.0, path=44.7m, goal_dist=0.026m, time=17.05s`、`benchmark_autoware = passed` を達成

---

## 4. 既知の制約

- Nav2 recovery セマンティクスが浅い (behavior tree status / action feedback の parse 未対応)
- Autoware の lanelet 評価は centerline のみ。corridor polygon / regulatory element 未対応
- ローカル trajectory は rolling。route-aware な真の追従評価は未完
- PointCloud2 clearance が optional `sensor_msgs_py` 依存
- Plotly がフロントエンドバンドルを支配 (lazy load 未)
- yaw_goal_tolerance はプロファイル定義済だが、`final_yaw_error` との突き合わせは部分的
- 実機ハードウェアデータでの検証ゼロ (sim と tutorial bag のみ)

---

## 5. 既存ロードマップ (README.md より)

- Multi-run benchmark dashboard (一部実装済)
- Route/lanelet-aware Autoware evaluation
- Nav2 behavior tree / recovery event parsing
- TF health checks と transform latency metrics
- Costmap layer diffing と time-synchronized overlays
- Failure clustering across simulation sweeps
- LLM-ready diagnosis packs (compact evidence window)
- GitHub Actions benchmark gates (一部実装済)

---

## 6. リポジトリ構造

```
NavigationAnalyzer/
  backend/navigation_analyzer/
    models.py            # canonical schema (NavigationRun / MetricResult / FailureFinding / DiagnosticFinding)
    io/                  # reader.py, rosbag2.py, unitree_record_nav.py
    analysis/            # metrics.py, failures.py, diagnostics.py, lanelet2.py, engine.py
    benchmarking/        # thresholds.py
    reporting/markdown.py
    api/                 # FastAPI server
    cli/main.py          # Typer entry
  frontend/src/
    App.tsx, types.ts, lib/api.ts
    components/{TrajectoryScene, MetricDashboard, FailureTimeline, BenchmarkDashboard}.tsx
  config/                # default.yaml / autoware.yaml / benchmark_*.yaml
  docs/                  # architecture, decisions, interfaces, benchmarking, experiments, simulation, autoware
  examples/              # 小さい canonical fixture (sample_bag, nav2_sim_success_003)
  scripts/               # record_*, analyze_*, run_*, run_sample_demo
  tests/                 # pytest (metrics, diagnostics, thresholds, lanelet2, fixtures)
```

コミット履歴は 4 つ:
1. Initial MVP
2. Diagnostics layer
3. Diagnostic benchmark gates
4. Unitree record_nav importer

---

## 7. キーとなる canonical schema (抜粋)

```python
class NavigationRun(BaseModel):
    run_id: str
    source: str
    goal: Point2D | None = None
    goal_pose: Pose2D | None = None
    planned_path: list[Point2D] = []
    samples: list[NavigationSample]    # t, pose, cmd_v, cmd_w, goal_distance, obstacle_distance, collision, recovery_event, localization_error
    costmap: Costmap | None = None
    metadata: dict[str, Any] = {}      # route_summary, planned_path_topic, etc.
```

このスキーマが拡張ポイント。ここを太らせる/分割するかが大きな設計判断になる。

---

## 8. 自分が悩んでいるところ (GPT-pro に聞きたい論点)

### A. ポジショニング
- 「観測 (Datadog 風)」「回帰評価 (CI gate)」「AI 可読診断」のうち、どれを最初に "刺さるもの" にすべきか?
- foxglove / PlotJuggler / Autoware evaluator / Nav2 内蔵 ツール群 と棲み分けるための **1 つの強い軸** は何にするべきか?
- "LLM 可読" を売りにする場合、診断 JSON はどんな形なら本当に LLM エージェントから扱いやすいのか (evidence window のサイズ、causal hypothesis の付け方、etc.)?

### B. データソース戦略
- 現状 sim/tutorial bag のみ。実機データを取りに行くなら何から始めるべき?
- unitree go2 / spot / turtlebot4 のような市販プラットフォームを「公式サポート」する価値はある?
- Nav2 と Autoware で「両対応」を続けるか、片方に賭けて深掘りするか?

### C. アナリシスの深掘り方向
1. **Causal 失敗解析** — 現在の rule-based を超えて、複数 evidence を束ねた hypothesis ranker を入れる?
2. **ML/LLM 分類器** — rule-based の上に学習レイヤを足すなら、どこから (failure clustering? root cause LLM?) 始めるべき?
3. **Counterfactual / What-if** — パラメータ変えたら何が起きたか、をシミュレータ抜きで近似する道はある?
4. **TF health / latency / coverage metrics** — robotics-specific な観測軸として優先する価値は?
5. **Costmap diffing と semantic overlay** — 視覚的に強いが、誰が使うか?

### D. 配布 / コミュニティ戦略
- pip パッケージ + docker image だけで足りるか? VSCode 拡張、Jupyter ウィジェット、GitHub Actions の market place エントリ、どれが効くか?
- LLM ツール (Claude Code / Cursor) から呼ぶ MCP server 化に投資する価値は?
- 「サンプル bag のショーケース」をどこにどう置くと OSS として広まるか?

### E. 商業化の余地 (もし考えるなら)
- 同種 OSS で商業化に成功してる事例 (Sentry / Datadog / Weights & Biases 流) を robotics でやるとしたら、何を SaaS にする?
- 逆に SaaS にしない方が伸びるか? (OSS 純度を保つ方向)

### F. 短期 (1〜2 週間) で投資するなら何?
- いま 4 コミットしか積んでない MVP 段階で、**次の 10 コミット** で何を入れると外から見て「これは違う」になるか?

---

## 9. 検証済みの数値スナップショット

```text
Nav2 sim fixture (turtlebot3 + nav2):
  success_rate = 1.0, path = 0.721 m, time = 3.744 s
  final_yaw_error = 0.191 rad
  failure_types = ["narrow_passage_failure"]

Autoware planning sim (sample-map, headless):
  success_rate = 1.0, path = 44.708 m, goal_distance = 0.026 m
  time_to_goal = 17.050 s, final_stopped_duration = 140.9 s
  benchmark_autoware = passed
```

---

## 10. 制約条件 (実情)

- 開発者 1 名 + AI コーディング併用、コミットペースは数日に 1 機能
- 実機ロボットは現時点で手元になし。sim と公開ログのみ
- 「最低限の OSS としての完成度 + 観測軸での独自性」で勝負する想定
- Python と TS の二段構成は維持したい (バックエンドは Python、UI は Web)

---

以上が現状です。**「これから 1〜3 ヶ月で何に投資すべきか」「捨てるべき方向」「効きそうな差別化」** について、GPT-pro 視点での率直な意見をください。
