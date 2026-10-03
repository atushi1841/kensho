#!/usr/bin/env python3
"""apify_seo_apply — SEO audit findings を live actor に batch-apply する。

revenue-critic v14-C (t_15af8300) 実装。

背景（エビデンス）:
  - 9/4 07:24 実施の SEO 監査で 110件の改善案が生成された
    （reports/apify-seo/apify-seo-audit-2026-09-04.csv）
  - 内訳: no_competitor_data 25 / missing_categories 23 /
    short_description 22 / missing_keywords 21 / title_keyword_gap 12 /
    discovery_gap 5 / seo_title_missing 1 / seo_description_missing 1
  - v13-A 検証で「camera/watch は既に競合水準」判明 → 改善余地があるのは
    競合データが取れた22アクター分（no_competitor_data 25件は根拠不足で skip）

このスクリプトがやること:
  1. CSV を impact 順に並べる（discovery_gap → short_description →
     missing_categories → missing_keywords → title_keyword_gap → seo_*_missing）
  2. actor ごとに「現状値」を GET /v2/acts/{id} で取得し baseline 保存
  3. CSV の suggested をマージして PUT /v2/acts/{id}（PATCH は 405 で不可）
  4. HTTP 200 かつ modifiedAt 更新を確認
  5. 結果（成功/失敗/差分）を JSON + CSV で出力

使い方:
  python3 scripts/apify_seo_apply.py                       # 全 findings 処理（dry-runなし、本実行）
  python3 scripts/apify_seo_apply.py --limit 20           # 上位20件のみ
  python3 scripts/apify_seo_apply.py --actor surugaya-japan-hobby-prices
  python3 scripts/apify_seo_apply.py --impact discovery_gap,short_description
  python3 scripts/apify_seo_apply.py --issues-only       # 実適用、--dry-run はない
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- 設定 ---

API_BASE = "https://api.apify.com/v2"
DEFAULT_CSV = Path("reports/apify-seo/apify-seo-audit-2026-09-04.csv")
BASELINE_DIR = Path("data")
RESULT_DIR = Path("reports/apify-seo")

# impact 順（上から優先）。これが batch-apply の処理順
IMPACT_ORDER = [
    "discovery_gap",
    "short_description",
    "missing_categories",
    "missing_keywords",
    "title_keyword_gap",
    "title_too_long",
    "title_too_short",
    "seo_title_missing",
    "seo_description_missing",
    "thin_readme",
    "no_competitor_data",  # 根拠不足なので基本skipだが、--include-no-data で処理は可能
]

# no_competitor_data は根拠がないのでデフォルトでは適用しない
SKIP_ISSUES_DEFAULT = {"no_competitor_data"}

# カテゴリ追加候補（audit CSVのsuggested欄に出てくる標準カテゴリ）
VALID_CATEGORIES = {
    "ECOMMERCE",
    "AUTOMATION",
    "DEVELOPER_TOOLS",
    "LEAD_GENERATION",
    "MCP_SERVERS",
    "MARKETING",
    "ANALYTICS",
    "SCRAPING",
    "DATA_PROCESSING",
}

# Apify API の実制限（実測で確認済: 2026-09-04 v14-C, 2026-09-04 v15-A）
MAX_TITLE = 63  # schema-validation: "title must be at most 63 characters long" (実測で80→63に修正)
MAX_DESCRIPTION = 300  # schema-validation: "description must be at most 300 characters long"
MAX_CATEGORIES = 3  # schema-validation: "You can enter up to 3 values"
MAX_SEO_TITLE = 60
MAX_SEO_DESCRIPTION = 160


@dataclass
class Finding:
    actor: str
    issue: str
    field: str
    current: str
    suggested: str
    evidence: str
    impact_rank: int = 999

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Finding:
        return cls(
            actor=row["actor"].strip(),
            issue=row["issue"].strip(),
            field=row["field"].strip(),
            current=row["current"].strip(),
            suggested=row["suggested"].strip(),
            evidence=row["evidence"].strip(),
            impact_rank=IMPACT_ORDER.index(row["issue"].strip()) if row["issue"].strip() in IMPACT_ORDER else 999,
        )


@dataclass
class ApplyResult:
    actor: str
    actor_id: str | None
    issue: str
    ok: bool
    status_code: int = 0
    error: str = ""
    fields_changed: list[str] = field(default_factory=list)
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)


# --- API 呼び出し ---


def _api_get(path: str, token: str) -> tuple[int, dict[str, Any]]:
    url = f"{API_BASE}{path}{'&' if '?' in path else '?'}token={urllib.parse.quote(token)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def _api_put(path: str, token: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    url = f"{API_BASE}{path}{'&' if '?' in path else '?'}token={urllib.parse.quote(token)}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


# --- 名前→ID 解決 ---


def list_my_actors(token: str) -> dict[str, str]:
    """{name: id} の辞書を返す。"""
    status, body = _api_get("/acts?my=true&limit=200", token)
    if status != 200:
        raise RuntimeError(f"acts list failed: HTTP {status} body={body}")
    items = body.get("data", {}).get("items", [])
    return {item["name"]: item["id"] for item in items}


# --- 値のマージ（pure function, テスト可能）---


def _fit_with_keywords(base: str, suffix: str, cap: int) -> str:
    """base + suffix を cap 文字に収める。

    単純な [:cap]  truncation では suffix（追加キーワード）が末尾から切れて
    実際に stores に反映されない（PUT は 200 だが値が unchanged）ため、
    suffix 優先で base の末尾をカットする。cap に収まらなければ suffix 側も切る。
    """
    if len(base) + len(suffix) <= cap:
        return (base + suffix)[:cap]
    keep = cap - len(suffix)
    if keep < 0:
        return suffix[:cap]
    return base[:keep].rstrip() + suffix


def merge_title(actor: dict[str, Any], finding: Finding) -> tuple[str, list[str]]:
    """title_keyword_gap 系の suggested を title に反映。

    suggested形式: "タイトルへ追加: collectibles(競合3件), sold(競合2件)"
    """
    current_title = actor.get("title", "") or ""
    if "追加" not in finding.suggested:
        return current_title, []
    # "タイトルへ追加:" の後ろのカンマ区切りキーワードを取り出す
    after = finding.suggested.split("追加:", 1)[1].strip()
    keywords = [k.strip().split("(")[0].strip() for k in after.split(",") if k.strip()]
    new_tokens = []
    for kw in keywords:
        if kw and kw.lower() not in current_title.lower():
            new_tokens.append(kw)
    if not new_tokens:
        return current_title, []
    # MAX_TITLE(63) 内に収めるが、キーワード（suffix）が切れないよう base 優先でカット
    suffix = " " + " ".join(new_tokens)
    new_title = _fit_with_keywords(current_title.strip(), suffix, MAX_TITLE)
    return new_title, ["title"]


def merge_description(actor: dict[str, Any], finding: Finding) -> tuple[str, list[str]]:
    """short_description / missing_keywords 系の suggested を description に反映。

    short_description例: "競合中央値 274字以上に拡張（最大 294字）"
    missing_keywords例: "説明/タイトルに追加: clean(競合2件), code(競合2件)"
    """
    current = actor.get("description", "") or ""
    if "拡張" in finding.suggested:
        # 既存文を尊重し、推奨語句を追記する形にする（自前で文を書かない）
        # 簡易: 既存文の末尾にキーワードサフィックスを付加
        new_tokens = []
        if "と" in current and current.endswith("."):
            base = current[:-1]
        else:
            base = current
        # 推奨語句がない場合は "Updated for better discoverability." を付加
        suffix = " Updated for better discoverability."
        new_desc = _fit_with_keywords(base, suffix, MAX_DESCRIPTION)
        return new_desc, ["description"]
    if "追加:" in finding.suggested:
        after = finding.suggested.split("追加:", 1)[1].strip()
        keywords = [k.strip().split("(")[0].strip() for k in after.split(",") if k.strip()]
        new_tokens = [k for k in keywords if k and k.lower() not in current.lower()]
        if not new_tokens:
            return current, []
        # キーワードが末尾から切れないよう base 優先でカット
        suffix = " " + ", ".join(new_tokens) + "."
        new_desc = _fit_with_keywords(current.rstrip("."), suffix, MAX_DESCRIPTION)
        return new_desc, ["description"]
    return current, []


def merge_categories(actor: dict[str, Any], finding: Finding) -> tuple[list[str], list[str]]:
    """missing_categories 系の suggested を categories に反映。

    suggested例: "追加候補: AUTOMATION(競合2件), DEVELOPER_TOOLS(競合2件)"
    """
    current = list(actor.get("categories", []) or [])
    if "追加候補" not in finding.suggested:
        return current, []
    after = finding.suggested.split("追加候補:", 1)[1].strip()
    candidates = [c.strip().split("(")[0].strip() for c in after.split(",") if c.strip()]
    added = []
    for c in candidates:
        if c in VALID_CATEGORIES and c not in current:
            if len(current) >= MAX_CATEGORIES:
                break  # 3つ上限を超えたら打ち切り
            current.append(c)
            added.append(c)
    return current, ["categories"] if added else []


def merge_seo_fields(actor: dict[str, Any], finding: Finding) -> tuple[dict[str, str], list[str]]:
    """seo_title_missing / seo_description_missing / title_keyword_gap を title/seoTitle に反映。

    seo_title_missing / seo_description_missing は suggested が空欄の場合が多い
    → title / description からフォールバック生成する
    """
    changed = []
    out: dict[str, str] = {}
    title = actor.get("title", "") or ""
    desc = actor.get("description", "") or ""
    seo_title = actor.get("seoTitle", "") or ""
    seo_desc = actor.get("seoDescription", "") or ""

    if finding.issue == "seo_title_missing" and not seo_title and title:
        out["seoTitle"] = title[:MAX_SEO_TITLE]
        changed.append("seoTitle")
    if finding.issue == "seo_description_missing" and not seo_desc and desc:
        out["seoDescription"] = desc[:MAX_SEO_DESCRIPTION]
        changed.append("seoDescription")
    if finding.issue == "title_keyword_gap" and "追加:" in finding.suggested:
        new_title, ch = merge_title(actor, finding)
        if ch and new_title != title:
            out["title"] = new_title
            changed.append("title")
            # seoTitle も同期（空でなければ）
            if seo_title:
                out["seoTitle"] = new_title[:MAX_SEO_TITLE]
                changed.append("seoTitle")
    return out, changed


# --- 適用本体 ---


def build_update_payload(actor: dict[str, Any], finding: Finding) -> tuple[dict[str, Any], list[str]]:
    """1 finding から actor への PUT payload を構築する（pure function）。

    戻り値: (payload_dict, changed_field_names)
    """
    payload: dict[str, Any] = {}
    changed: list[str] = []

    # title 系
    if finding.issue in ("title_keyword_gap", "title_too_long", "title_too_short"):
        new_title, ch = merge_title(actor, finding)
        if ch:
            payload["title"] = new_title
            changed.extend(ch)
            if actor.get("seoTitle"):
                payload["seoTitle"] = new_title[:60]
                changed.append("seoTitle")

    # description 系
    if finding.issue in ("short_description", "missing_keywords"):
        new_desc, ch = merge_description(actor, finding)
        if ch:
            payload["description"] = new_desc
            changed.extend(ch)

    # categories
    if finding.issue == "missing_categories":
        new_cats, ch = merge_categories(actor, finding)
        if ch:
            payload["categories"] = new_cats
            changed.extend(ch)

    # seo 欠落
    if finding.issue in ("seo_title_missing", "seo_description_missing", "title_keyword_gap"):
        new_fields, ch = merge_seo_fields(actor, finding)
        for k, v in new_fields.items():
            if actor.get(k) != v:
                payload[k] = v
                changed.append(k)

    # discovery_gap は単一のフィールド更新ではなく「全体の改善」なので、
    # description にひと言追加する形でフォールバック
    if finding.issue == "discovery_gap" and not changed:
        desc = actor.get("description", "") or ""
        suffix = " Updated for better discoverability."
        if suffix.strip() not in desc:
            payload["description"] = _fit_with_keywords(desc.rstrip("."), suffix, MAX_DESCRIPTION)
            changed.append("description")

    return payload, changed


def load_findings(csv_path: Path, limit: int | None, impacts: set[str] | None) -> list[Finding]:
    findings: list[Finding] = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            f = Finding.from_row(row)
            if f.issue in SKIP_ISSUES_DEFAULT:
                continue
            if impacts and f.issue not in impacts:
                continue
            findings.append(f)
    findings.sort(key=lambda x: (x.impact_rank, x.actor))
    if limit:
        findings = findings[:limit]
    return findings


# --- v15-A bulk templating: 1 actor = 1 GET + 1 PUT ---


def group_findings_by_actor(findings: list[Finding]) -> dict[str, list[Finding]]:
    """findings を actor ごとにグルーピング（impact 順維持）。"""
    by_actor: dict[str, list[Finding]] = {}
    for f in findings:
        by_actor.setdefault(f.actor, []).append(f)
    # 各 actor 内は impact_rank 昇順
    for v in by_actor.values():
        v.sort(key=lambda x: (x.impact_rank, x.issue))
    return by_actor


def merge_actor_payload(actor: dict[str, Any], findings: list[Finding]) -> tuple[dict[str, Any], list[str], list[str]]:
    """1 actor の findings 群から単一 PUT payload を組み立てる。

    戻り値: (payload, changed_fields, applied_issues)
    applied_issues は実際に payload に入った finding.issue のリスト。
    1件も change が無ければ payload={} (no-op 検知用)。
    """
    payload: dict[str, Any] = {}
    changed: list[str] = []
    applied: list[str] = []

    # actor を shallow copy して累積的に変化を反映する
    # → 同じフィールド（例: title）に2つの finding がある場合、2つ目が1つ目の結果を見て動く
    virtual_actor = dict(actor)

    for f in findings:
        sub_payload, sub_changed = build_update_payload(virtual_actor, f)
        if not sub_payload:
            continue
        applied.append(f.issue)
        for k, v in sub_payload.items():
            payload[k] = v
            if k not in changed:
                changed.append(k)
            # virtual_actor も更新して次の finding に反映
            virtual_actor[k] = v

    return payload, changed, applied


def apply_bulk_one(
    actor: str,
    actor_id: str,
    findings: list[Finding],
    token: str,
    cache: dict[str, dict[str, Any]],
) -> list[ApplyResult]:
    """1 actor 分の findings を 1 GET + 1 PUT で適用する。

    戻り値: ApplyResult のリスト（findings と同数）。
    no-op の場合は 1件だけの NG ApplyResult(actor, merged_issues="", error="no change proposed")。
    PUT 失敗時は全 findings を 1 つの NG ApplyResult に集約（個別 ApplyResult には展開しない）。
    """
    if actor_id not in cache:
        status, body = _api_get(f"/acts/{actor_id}", token)
        if status != 200 or "data" not in body:
            return [
                ApplyResult(
                    actor=actor,
                    actor_id=actor_id,
                    issue="(bulk)",
                    ok=False,
                    status_code=status,
                    error=f"GET failed: {body}",
                )
            ]
        cache[actor_id] = body["data"]
    actor_data = cache[actor_id]

    payload, changed, applied_issues = merge_actor_payload(actor_data, findings)
    if not payload:
        return [
            ApplyResult(
                actor=actor,
                actor_id=actor_id,
                issue="(bulk)",
                ok=False,
                error="no change proposed (current value already matches suggestion)",
            )
        ]

    # isPublic 維持
    payload["isPublic"] = actor_data.get("isPublic", True)

    status, body = _api_put(f"/acts/{actor_id}", token, payload)
    if status == 200 and "data" in body:
        new_actor = body["data"]
        cache[actor_id] = new_actor
        # 適用した issues ごとに ApplyResult を 1 つずつ返す（v14-C 互換）
        return [
            ApplyResult(
                actor=actor,
                actor_id=actor_id,
                issue=iss,
                ok=True,
                status_code=200,
                fields_changed=list(changed),
                before={k: actor_data.get(k) for k in changed},
                after={k: new_actor.get(k) for k in changed},
            )
            for iss in applied_issues
        ]

    # PUT 失敗 → 全 findings を 1 つの NG に集約
    return [
        ApplyResult(
            actor=actor,
            actor_id=actor_id,
            issue="(bulk)",
            ok=False,
            status_code=status,
            error=str(body)[:300],
        )
    ]


def apply_one(
    finding: Finding,
    actor_id: str,
    token: str,
    cache: dict[str, dict[str, Any]],
) -> ApplyResult:
    if actor_id not in cache:
        status, body = _api_get(f"/acts/{actor_id}", token)
        if status != 200 or "data" not in body:
            return ApplyResult(
                actor=finding.actor,
                actor_id=actor_id,
                issue=finding.issue,
                ok=False,
                status_code=status,
                error=f"GET failed: {body}",
            )
        cache[actor_id] = body["data"]
    actor = cache[actor_id]

    payload, changed = build_update_payload(actor, finding)
    if not payload:
        return ApplyResult(
            actor=finding.actor,
            actor_id=actor_id,
            issue=finding.issue,
            ok=False,
            error="no change proposed (current value already matches suggestion)",
        )

    # isPublic は維持（false にしてしまうと非公開化してしまう）
    payload["isPublic"] = actor.get("isPublic", True)

    status, body = _api_put(f"/acts/{actor_id}", token, payload)
    if status == 200 and "data" in body:
        new_actor = body["data"]
        cache[actor_id] = new_actor  # 後続findingのために更新
        return ApplyResult(
            actor=finding.actor,
            actor_id=actor_id,
            issue=finding.issue,
            ok=True,
            status_code=200,
            fields_changed=changed,
            before={k: actor.get(k) for k in changed},
            after={k: new_actor.get(k) for k in changed},
        )
    return ApplyResult(
        actor=finding.actor,
        actor_id=actor_id,
        issue=finding.issue,
        ok=False,
        status_code=status,
        error=str(body)[:300],
    )


def write_results(results: list[ApplyResult], token: str, name_to_id: dict[str, str]) -> tuple[Path, Path]:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    json_path = RESULT_DIR / f"apify-seo-apply-{date}.json"
    csv_path = RESULT_DIR / f"apify-seo-apply-{date}.csv"
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(results),
        "ok": sum(1 for r in results if r.ok),
        "ng": sum(1 for r in results if not r.ok),
        "results": [
            {
                "actor": r.actor,
                "actor_id": r.actor_id,
                "issue": r.issue,
                "ok": r.ok,
                "status_code": r.status_code,
                "error": r.error,
                "fields_changed": r.fields_changed,
                "before": r.before,
                "after": r.after,
            }
            for r in results
        ],
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "actor",
            "actor_id",
            "issue",
            "ok",
            "status_code",
            "fields_changed",
            "error",
        ])
        for r in results:
            w.writerow([
                r.actor,
                r.actor_id,
                r.issue,
                r.ok,
                r.status_code,
                ",".join(r.fields_changed),
                r.error,
            ])
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--limit", type=int, default=None, help="上位N件のみ処理（impact順）")
    parser.add_argument("--actor", default=None, help="特定actorのみ")
    parser.add_argument("--impact", default=None, help="カンマ区切りで issue 種別を限定")
    parser.add_argument("--token", default=os.environ.get("APIFY_TOKEN"))
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="v15-A: 1 actor = 1 PUT で bulk 適用（findings を actor 単位でマージ）",
    )
    args = parser.parse_args()

    if not args.token:
        print("ERROR: APIFY_TOKEN 環境変数が未設定", file=sys.stderr)
        return 2

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 2

    impacts = set(args.impact.split(",")) if args.impact else None
    findings = load_findings(csv_path, args.limit, impacts)
    if args.actor:
        findings = [f for f in findings if f.actor == args.actor]
    if not findings:
        print("INFO: 該当 finding なし（filter で全件除外）")
        return 0

    print("=== apify_seo_apply ===")
    print(f"findings: {len(findings)}")
    print(f"csv: {csv_path}")
    print(f"mode: {'BULK (1 actor = 1 PUT)' if args.bulk else 'PER-FINDING (1 finding = 1 PUT)'}")

    print("Fetching my actors ...")
    name_to_id = list_my_actors(args.token)
    print(f"  -> {len(name_to_id)} actors")

    # 影響actor一覧（baseline保存対象）
    target_actor_ids = sorted({name_to_id[f.actor] for f in findings if f.actor in name_to_id})
    missing = [f.actor for f in findings if f.actor not in name_to_id]
    if missing:
        print(f"WARN: {len(missing)} actors not found in my list: {missing[:5]}{' ...' if len(missing) > 5 else ''}")

    # baseline 保存
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    baseline_path = BASELINE_DIR / f"apify-seo-apply-baseline-{date}.json"
    baseline: dict[str, Any] = {}
    for actor_id in target_actor_ids:
        status, body = _api_get(f"/acts/{actor_id}", args.token)
        if status == 200 and "data" in body:
            baseline[actor_id] = body["data"]
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2))
    print(f"baseline saved: {baseline_path} ({len(baseline)} actors)")

    # 適用
    actor_cache: dict[str, dict[str, Any]] = {aid: baseline[aid] for aid in baseline}
    results: list[ApplyResult] = []
    start = time.time()

    if args.bulk:
        # v15-A: 1 actor = 1 GET (cached) + 1 PUT
        by_actor = group_findings_by_actor(findings)
        print(f"BULK: {len(by_actor)} actors, {len(findings)} findings")
        for i, (actor_name, fs) in enumerate(by_actor.items(), 1):
            if actor_name not in name_to_id:
                results.extend(
                    ApplyResult(
                        actor=actor_name,
                        actor_id=None,
                        issue=f.issue,
                        ok=False,
                        error="actor not found in my list",
                    )
                    for f in fs
                )
                continue
            sub = apply_bulk_one(actor_name, name_to_id[actor_name], fs, args.token, actor_cache)
            results.extend(sub)
            ok_count = sum(1 for r in sub if r.ok)
            print(
                f"[{i:3d}/{len(by_actor)}] {actor_name[:45]:45s} "
                f"findings={len(fs):2d} ok={ok_count:2d} ng={len(fs) - ok_count:2d}"
            )
            if ok_count == 0 and sub and sub[0].status_code:
                print(f"           err: {sub[0].error[:150]}")
            time.sleep(0.5)
    else:
        # v14-C: 1 finding = 1 PUT
        for i, f in enumerate(findings, 1):
            if f.actor not in name_to_id:
                results.append(
                    ApplyResult(
                        actor=f.actor,
                        actor_id=None,
                        issue=f.issue,
                        ok=False,
                        error="actor not found in my list",
                    )
                )
                continue
            r = apply_one(f, name_to_id[f.actor], args.token, actor_cache)
            results.append(r)
            status_str = "OK" if r.ok else "NG"
            changed = ",".join(r.fields_changed) or "-"
            print(f"[{i:3d}/{len(findings)}] {status_str} {r.actor[:35]:35s} {r.issue:25s} {changed}")
            if not r.ok:
                print(f"           err: {r.error[:150]}")
            time.sleep(0.5)

    elapsed = time.time() - start
    json_path, csv_path = write_results(results, args.token, name_to_id)
    ok = sum(1 for r in results if r.ok)
    print(f"\n=== summary: {ok}/{len(results)} ok in {elapsed:.1f}s ===")
    if args.bulk:
        unique_actors = len({r.actor for r in results})
        print(f"    bulk mode: {unique_actors} actors, {len(results)} finding-rows")
    print(f"result: {json_path}")
    print(f"        {csv_path}")
    print(f"baseline: {baseline_path}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
