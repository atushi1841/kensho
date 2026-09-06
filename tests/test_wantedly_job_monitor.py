"""tests/test_wantedly_job_monitor.py — Wantedly 求人監視ツールのテスト."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import wantedly_job_monitor as wd  # noqa: E402


def _ssr_html(job_ids, detail):
    """最小 SSR 埋め込み HTML を合成する (graphqlGatewayInitialState 形式)。"""
    initial = {
        "ROOT_QUERY": {
            "__typename": "Query",
            "projectIndexPageJobPostIndex": {
                "__typename": "ProjectIndexPageJobPostIndex",
                'searchedJobPostsUsingOffset({"input":{"pageNumber":1,"pageSize":10,"searchParameters":null}})': {
                    "jobPosts": [{"jobPost": {"__ref": f'JobPost:{{"id":"{i}"}}'}} for i in job_ids]
                },
            },
        }
    }
    for jid, d in detail.items():
        initial[f'JobPost:{{"id":"{jid}"}}'] = d
    next_data = {"props": {"pageProps": {"__apollo": {"graphqlGatewayInitialState": initial}}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'


def _mkdetail(
    title="Rustエンジニア募集", company="Test社", occ="Rustエンジニア", published="2026-09-05T00:00:00.000Z", types=None
):
    return {
        "__typename": "JobPost",
        "id": "999",
        "title": title,
        "occupationName": occ,
        "publishedAt": published,
        "detailDescription": {"__typename": "JobPostDescription", "plainBody": "説明文"},
        "company": {"__typename": "Company", "name": company, "slug": "company_x"},
        "hiringTypes": [{"type": t, "label": t} for t in (types or ["mid_career"])],
    }


def test_parse_ssr_extracts_jobs_with_metadata():
    html = _ssr_html(["999"], {"999": _mkdetail()})
    jobs = wd.parse_ssr(html)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.id == "999"
    assert j.title == "Rustエンジニア募集"
    assert j.company == "Test社"
    assert j.occupation == "Rustエンジニア"
    assert j.hiring_types == ["mid_career"]
    assert j.url == "https://www.wantedly.com/projects/999"


def test_parse_ssr_ignores_duplicate_ids():
    # 同じ id が検索結果に複数現れても 1 回だけ
    html = _ssr_html(
        ["999", "999", "1000"],
        {
            "999": _mkdetail(),
            "1000": _mkdetail(title="別の求人"),
        },
    )
    jobs = wd.parse_ssr(html)
    assert [j.id for j in jobs] == ["999", "1000"]


def test_ref_id_handles_dict_and_str():
    assert wd._ref_id({"__ref": 'JobPost:{"id":"123"}'}) == "123"
    assert wd._ref_id('JobPost:{"id":"456"}') == "456"
    assert wd._ref_id("garbage") is None
    assert wd._ref_id(None) is None


def test_build_url_encodes_filters():
    q = wd.Query(
        keywords=["Rustエンジニア"], areas=["tokyo", "osaka"], hiring_types=["mid_career"], order="recent", pages=2
    )
    url = wd.build_url(q, 2)
    assert "keywords=Rust%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2" in url
    assert "areas=tokyo" in url
    assert "areas=osaka" in url
    assert "hiringTypes=mid_career" in url
    assert "order=recent" in url
    assert "page=2" in url


def test_sqlite_dedup_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(wd, "STATE_DB", tmp_path / "state.db")
    conn = wd.get_db()
    assert not wd.is_seen(conn, "999")
    wd.mark_seen(conn, "999", "2026-09-05T00:00:00.000Z", "テ kingT")
    conn.commit()
    assert wd.is_seen(conn, "999")
    conn.close()


def test_fmt_notify_contains_url_and_title():
    q = wd.Query(keywords=["Rust"])
    j = wd.JobPost(
        "999",
        "Rustエンジニア募集",
        "Test社",
        "Rustエンジニア",
        ["mid_career"],
        "2026-09-05T00:00:00.000Z",
        "https://www.wantedly.com/projects/999",
    )
    text = wd.fmt_notify(q, j)
    assert "Rustエンジニア募集" in text
    assert "https://www.wantedly.com/projects/999" in text
    assert "Test社" in text
