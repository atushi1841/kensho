#!/usr/bin/env python3
"""kensho-opportunity-discovery — 収益機会の自動発見プロンプト生成。

毎朝cronで実行され、X(Twitter)/Web/5ch/Apify Storeから
収益機会を自動収集・評価するための調査プロンプトをstdoutに出力する。
cronジョブのagentがこのプロンプトに従って検索→評価→Kanban投入まで自動実行する。

「ユーザーがほとんど指示しなくても収益システムが回る」ための
収益機会発見レイヤー。monetization-pipeline(毎日9時)と連携し、
新規収益ネタの供給を絶やさない。
"""

import datetime
import hashlib
import sys

# ── 収益機会カテゴリ（日替わりローテーション） ─────────────
CATEGORIES = [
    {
        "id": 1,
        "name": "データ販売（Apify/Gumroad）",
        "focus": "日本市場のデータで海外需要があり、競合が少ない未開拓ターゲット",
        "sources": ["xsearch", "web_search", "apify_store"],
        "keywords": [
            "japan data api apify",
            "japanese market scraper demand",
            "Gumroad dataset sales",
            "データセット 販売 収益",
            "japan hobby market data",
        ],
        "evaluate": "技術実装可否・TOSリスク（大企業/公式APIありは即却下）・競合数、需要シグナル（Reddit/Xの実声・プロキシ代行の存在）",
    },
    {
        "id": 2,
        "name": "API収益化（RapidAPI/MCP）",
        "focus": "RapidAPIやMCPサーバーとして提供できるAPIの需要と価格帯",
        "sources": ["web_search", "github", "xsearch"],
        "keywords": [
            "RapidAPI monetization 2026",
            "MCP server revenue",
            "pay per event API revenue",
            "API marketplace passive income",
            "AI agent call API monetize",
        ],
        "evaluate": "既存資産（Apify 58本/RapidAPI 20本）で実現可能か・PPE単価の妥当性、AIエージェントからの発見可能性（README最適化）",
    },
    {
        "id": 3,
        "name": "懸賞・ポイ活の新動向",
        "focus": "高額当選・新規懸賞サイト・効率の良い応募手法の出現",
        "sources": ["xsearch", "fch", "web_search"],
        "keywords": [
            "懸賞 当選 2026",
            "プレゼント 応募 高額",
            "ポイントサイト 還元",
            "懸賞 新着 サイト",
            "ポイ活 稼げる",
        ],
        "evaluate": "Kenshoの既存パイプラインに即組み込めるか・当選確率向上につながるか・収集ソース追加の価値",
    },
    {
        "id": 4,
        "name": "ニッチSaaS・自動化ツール",
        "focus": "価格追跡・通知・データ監視など小さな自動化サービスの需要",
        "sources": ["web_search", "hn", "xsearch"],
        "keywords": [
            "niche SaaS 2026",
            "price tracking service demand",
            "automation tool side project revenue",
            "indie hacker revenue 2026",
            "個人開発 収益化",
        ],
        "evaluate": "需要の実証（競合・ユーザー声）・開発コスト・収益単価・月1-3万円達成に現実的か",
    },
    {
        "id": 5,
        "name": "AIエージェント経済圏",
        "focus": "AIエージェントが自動で呼び出すデータ/ツール需要の増加",
        "sources": ["web_search", "github", "hn"],
        "keywords": [
            "AI agent data demand 2026",
            "MCP server marketplace",
            "agent skills monetization",
            "LLM tool discovery",
            "AIエージェント 収益化",
        ],
        "evaluate": "MCP/Apify経由でAIエージェントに発見される仕組みに乗れるか・無料リードマグネット戦略の適用",
    },
]


def today_category() -> dict:
    """今日の日付からカテゴリを選ぶ（通し日数 % 5、2026-09-02起点）。

    --category N 引数で特定カテゴリ(1-5)を強制指定できる。
    """
    if "--category" in sys.argv:
        idx = int(sys.argv[sys.argv.index("--category") + 1]) - 1
        if 0 <= idx < len(CATEGORIES):
            return CATEGORIES[idx]
    start = datetime.date(2026, 9, 2)
    day = datetime.date.today()
    idx = (day - start).days % len(CATEGORIES)
    return CATEGORIES[idx]


def variant_seed(cat_id: int) -> str:
    """同じカテゴリでも日付によって検索ワードにバリエーションを持たせる。"""
    today = datetime.date.today().isoformat()
    return hashlib.md5(f"opp:{cat_id}:{today}".encode()).hexdigest()[:8]


def main():
    cat = today_category()
    seed = variant_seed(cat["id"])

    lines = []
    lines.append("【kensho-opportunity-discovery — 今日の収益機会調査】")
    lines.append(f"カテゴリ: {cat['name']}")
    lines.append(f"調査焦点: {cat['focus']}")
    lines.append(f"バリエーションシード: {seed}")
    lines.append("")
    lines.append("【調査ゴール】")
    lines.append(
        "「ユーザーがほとんど指示しなくても収益が出る」ための新規収益機会を発見し、"
        "実現可能なものはKanbanにreadyタスクとして投入する。"
    )
    lines.append("")
    lines.append("【対象情報源とアクセス方法】")
    lines.append("- web_search xsearch '<query>'   # X投稿検索")
    lines.append("- web_search search '<query>'   # DuckDuckGo一般検索")
    lines.append("- web_search fch '<keyword>'   # 5chスレッド検索")
    lines.append("- web_search fetch 'https://apify.com/store'   # Apify Store")
    lines.append("- web_search fetch 'https://github.com/trending'   # GitHubトレンド")
    lines.append("")
    lines.append("【検索キーワード例】（バリエーションシードを元に言い換えてもよい）")
    for kw in cat["keywords"]:
        lines.append(f"- {kw}")
    lines.append("")
    lines.append("【評価手順】")
    lines.append("1. 上記キーワードで最低3つの情報源を検索する")
    lines.append("2. ヒットした機会を以下で評価する:")
    lines.append(f"   - 評価軸: {cat['evaluate']}")
    lines.append("   - 技術的可否: 既存スキル/環境で実装可能か")
    lines.append("   - TOSリスク: 大企業+再利用禁止/公式APIありは即却下（feasibility-researchスキル参照）")
    lines.append("   - 需要: 実際に払う人がいるか（Xの実声・プロキシ代行・専用カテゴリ）")
    lines.append("   - 競合: Apify Store/GitHubで既存実装の有無")
    lines.append("3. 評価が通った機会は、実装手順を添えてKanbanにreadyタスクとして作成:")
    lines.append("   - 【必須・critic v162】起票前に必ず重複ガードを通す（同一テーマの二重登録防止）:")
    lines.append(
        "     `python3 /mnt/d/Project2/kensho/scripts/kensho_hunter_guard.py check"
        " --title '<タスク名>' --body '<本文要旨>'`"
    )
    lines.append("     - exit 1 (dup出力) = open状態に同一テーマあり → 起票中止。既存カードIDへ")
    lines.append(
        "       `hermes kanban comment <既存ID> '収益機会自動発見(YYYY-MM-DD): 再確認、本カードで追跡'`"
        " で代替（新規を作らない）"
    )
    lines.append("     - exit 2 = 幽霊assignee（実在しないassignee）→ 起票中止")
    lines.append("       `hermes kanban create ... --assignee <assignee>` は --assignee の後に")
    lines.append("       kensho_hunter_guard.py check --assignee <assignee> を自動的に実行")
    lines.append("       ことが要件")
    lines.append("   - exit 0 = stdout に決定的キー hunter-YYYYMMDD-<hash8> が出力される → それを流用:")
    lines.append(
        "   - hermes kanban create '<タスク名>' --assignee kensho-worker --ready"
        " --idempotency-key '<checkが出力したhunter-YYYYMMDD-...キー>'"
    )
    lines.append("   - キーなしでの kanban create は禁止（成功指標: worker発券の idempotency_key NULL = 0件）")
    lines.append("   - タスク内コメントに「収益機会自動発見(YYYY-MM-DD)」と評価結果を記録")
    lines.append("4. 評価が通らなかった機会は却下理由を簡潔に記録（再利用のため）")
    lines.append("")
    lines.append("【出力形式】")
    lines.append("## 収益機会発見レポート（YYYY-MM-DD / カテゴリ名）")
    lines.append("### 発見した機会（3件まで）")
    lines.append("- 機会内容 / 情報源URL / 需要シグナル / 競合状況 / 評価: 可/不可")
    lines.append("### Kanban投入結果")
    lines.append("- 作成したタスクIDと内容（あれば）")
    lines.append("### 却下した機会と理由")
    lines.append("- 機会内容 / 却下理由")
    lines.append("### 次回への申し送り")
    lines.append("- 深掘りすべき点・保留中の機会")

    print("\n".join(lines))


if __name__ == "__main__":
    main()