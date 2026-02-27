# try-multi-agent

Claude API (tool_use) を使ったマルチエージェントオーケストレーションフレームワークの実験。
12のエージェントロールが優先度付きパイプラインで協調し、シェアハウス管理基幹システムを開発する。

## 構成

### フレームワーク

| パッケージ | 役割 |
|---|---|
| `agents/` | Agent 基底クラス + 12 ロール定義 |
| `orchestrator/` | 優先度パイプライン（フェーズ順実行・並列制御） |
| `tools/` | ファイル I/O・シェル実行・メッセージング・タスク管理 |
| `workspace/` | 成果物の共有ワークスペース |

### 7 フェーズパイプライン

```
Phase 0 [CRITICAL]  要件定義        → PM
Phase 1 [HIGH]      設計            → システムアーキテクト + DBアーキテクト (並列)
Phase 2 [MEDIUM+]   実装            → バックエンド + フロントエンド (並列)
Phase 3 [MEDIUM]    レビュー・テスト → コードレビュー + テスト + セキュリティ (並列)
Phase 4 [MEDIUM]    インフラ        → インフラエンジニア
Phase 5 [LOW]       法令遵守        → 法務 + 税務 (並列)
Phase 6 [LOWEST]    ドキュメント    → ドキュメントライター
```

## セットアップ

```bash
# 依存インストール
uv sync

# 実行（ローカル）
ANTHROPIC_API_KEY=sk-ant-xxx uv run python main.py

# 実行（Docker — 推奨）
ANTHROPIC_API_KEY=sk-ant-xxx docker compose up --build
```

成果物は `workspace_output/` に出力される。

## コスト目安

- 12 エージェント × 平均 3–5 API コール ≈ 36–60 回
- Sonnet 使用時: 概算 $3–10
- 初回は `main.py` の `PHASES` を Phase 0–1 に絞って動作確認推奨
