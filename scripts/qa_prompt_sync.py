#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QA検証済み教訓（qa_passed）からcritic/worker/QA等のプロンプト/スキルを自動更新するパイプライン (t_ceb1faef).

RSI L2 (Recursive Self-Improvement Level 2) 持続的継承:
QA完了時の kanban_done_guard 通過済み教訓 (evidence.json / notepad lessons) を
テンプレート化したプロンプト断片として各プロファイルのスキル/プロンプトに重複なくパッチ適用・同期する。
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("qa_prompt_sync")

# 定数宣言
SYSTEM_PROFILES = [
    "kensho-sweeps",
    "kensho-critic",
    "kensho-worker",
    "kensho-qa",
    "kensho-revenue-critic",
    "kensho-revenue-worker",
    "kensho-revenue-qa",
]

TARGET_SKILL_REL = "skills/software-development/ai-team-improvement/SKILL.md"
LESSONS_SECTION_HEADER = "## QA検証済み教訓 (qa_passed Lessons)"
ROLLBACK_DIR_NAME = ".qa_prompt_sync_backups"

DEFAULT_HERMES_BASE = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).parent


def get_profile_dir(profile_name: str) -> Path:
    """指定プロファイルのディレクトリを取得する。"""
    base = Path.home() / ".hermes" / "profiles"
    return base / profile_name


def load_evidence_lessons(evidence_path: Path) -> List[Dict[str, str]]:
    """reports/<task_id>_evidence.json から教訓項目を取得する。"""
    if not evidence_path.exists():
        logger.warning(f"Evidence file not found: {evidence_path}")
        return []

    try:
        data = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse evidence JSON {evidence_path}: {e}")
        return []

    lessons = []
    # 1. evidence.json 内に明示的な lessons 配列/文字列がある場合
    if "lessons" in data:
        raw_lessons = data["lessons"]
        if isinstance(raw_lessons, list):
            for item in raw_lessons:
                if isinstance(item, str):
                    lessons.append({"text": item.strip(), "source": evidence_path.name})
                elif isinstance(item, dict) and "text" in item:
                    lessons.append({"text": str(item["text"]).strip(), "source": evidence_path.name})
        elif isinstance(raw_lessons, str) and raw_lessons.strip():
            lessons.append({"text": raw_lessons.strip(), "source": evidence_path.name})

    # 2. outcome_review や summary, findings から抽出可能な場合の補完
    if not lessons and "outcome" in data and isinstance(data["outcome"], dict):
        out = data["outcome"]
        metric = out.get("metric", "")
        before = out.get("before", "")
        after = out.get("after", "")
        if metric:
            lessons.append({
                "text": f"成果計測 [{metric}]: before={before} -> after={after}",
                "source": evidence_path.name,
            })

    return lessons


def extract_lessons_from_text(text: str, source_tag: str = "text") -> List[Dict[str, str]]:
    """箇条書きテキスト等から教訓項目を抽出する。"""
    lessons = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ")):
            clean_text = re.sub(r"^([-*]|\d+\.)\s*", "", line).strip()
            if clean_text:
                lessons.append({"text": clean_text, "source": source_tag})
    return lessons


def format_lesson_entry(lesson: Dict[str, str]) -> str:
    """教訓エントリを正規化フォーマット文字列（1行）にする。"""
    text = lesson.get("text", "").strip()
    source = lesson.get("source", "").strip()
    # 複数行改行は空白に置換
    text = " ".join(text.splitlines())
    if source:
        return f"- [前回教訓] {text} (ref: {source})"
    else:
        return f"- [前回教訓] {text}"


def backup_file(file_path: Path) -> Path:
    """ファイルをロールバック用にバックアップする。"""
    backup_dir = file_path.parent / ROLLBACK_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file_path = backup_dir / f"{file_path.name}.bak"
    backup_file_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_file_path


def restore_backup(file_path: Path) -> bool:
    """バックアップからリストア（ロールバック）する。"""
    backup_file_path = file_path.parent / ROLLBACK_DIR_NAME / f"{file_path.name}.bak"
    if not backup_file_path.exists():
        logger.error(f"Backup file not found for rollback: {backup_file_path}")
        return False
    file_path.write_text(backup_file_path.read_text(encoding="utf-8"), encoding="utf-8")
    logger.info(f"Restored backup to {file_path}")
    return True


def apply_lessons_to_skill(
    skill_path: Path, new_lessons: List[Dict[str, str]], dry_run: bool = False
) -> Tuple[bool, List[str]]:
    """SKILL.md に教訓パッチを重否定（重複適用防止）を適用する。

    戻り値: (変更があったか, 適用された教訓リスト)
    """
    if not skill_path.exists():
        logger.warning(f"Skill file not found: {skill_path}")
        return False, []

    content = skill_path.read_text(encoding="utf-8")

    # 既存の教訓セクションの取得または作成
    applied_count = 0
    added_formatted: List[str] = []

    # 重複判定用（既存コンテンツ内に類似テキストが存在するか）
    existing_normalized = content.lower()

    formatted_entries = []
    for item in new_lessons:
        formatted = format_lesson_entry(item)
        # 本文テキスト抽出して重複確認
        raw_text = item["text"].strip().lower()
        if raw_text in existing_normalized or formatted.lower() in existing_normalized:
            logger.info(f"Skip existing lesson (dedup): {item['text'][:40]}...")
            continue
        formatted_entries.append(formatted)
        added_formatted.append(formatted)

    if not formatted_entries:
        logger.info("No new unique lessons to apply.")
        return False, []

    if dry_run:
        logger.info(f"[DRY-RUN] Would append {len(formatted_entries)} lessons to {skill_path}")
        return True, added_formatted

    # バックアップ作成
    backup_file(skill_path)

    # パッチ適用ロジック
    if LESSONS_SECTION_HEADER in content:
        # 既存セクション直下に追記
        parts = content.split(LESSONS_SECTION_HEADER, 1)
        header_block = parts[0] + LESSONS_SECTION_HEADER + "\n"
        rest = parts[1]

        # 追記ブロック構築
        new_block = "\n".join(formatted_entries) + "\n"
        new_content = header_block + new_block + rest
    else:
        # ファイル末尾に新規セクションを作成して追加
        new_content = (
            content.rstrip()
            + f"\n\n{LESSONS_SECTION_HEADER}\n"
            + "\n".join(formatted_entries)
            + "\n"
        )

    skill_path.write_text(new_content, encoding="utf-8")
    logger.info(f"Successfully applied {len(formatted_entries)} lessons to {skill_path}")
    return True, added_formatted


def sync_all_profiles(
    evidence_path: Optional[Path] = None,
    raw_lessons_text: Optional[str] = None,
    profiles: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """全プロファイルの AI チームスキルに教訓を同期適用する。"""
    target_profiles = profiles or SYSTEM_PROFILES

    # 教訓の集約
    lessons: List[Dict[str, str]] = []
    if evidence_path:
        lessons.extend(load_evidence_lessons(evidence_path))

    if raw_lessons_text:
        lessons.extend(extract_lessons_from_text(raw_lessons_text, source_tag="manual_input"))

    if not lessons:
        return {"status": "skipped", "reason": "no_lessons_found", "applied_profiles": []}

    results = {}
    applied_profiles = []

    for prof in target_profiles:
        prof_dir = get_profile_dir(prof)
        skill_file = prof_dir / TARGET_SKILL_REL
        if not skill_file.exists():
            logger.debug(f"Skill file does not exist for profile {prof}: {skill_file}")
            continue

        changed, applied = apply_lessons_to_skill(skill_file, lessons, dry_run=dry_run)
        results[prof] = {"changed": changed, "applied": applied}
        if changed:
            applied_profiles.append(prof)

    return {
        "status": "success",
        "lessons_count": len(lessons),
        "applied_profiles": applied_profiles,
        "details": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="QA検証済み教訓からシステムプロンプト/スキルを自動更新するパイプライン"
    )
    parser.add_argument("--evidence", type=str, help="reports/<task_id>_evidence.json のパス")
    parser.add_argument("--text", type=str, help="直接追加する教訓テキスト (箇条書き可)")
    parser.add_argument("--profiles", nargs="+", help="対象プロファイル一覧 (デフォルト: 全AIチームプロファイル)")
    parser.add_argument("--dry-run", action="store_true", help="実際に変更を行わずに確認のみ行う")
    parser.add_argument("--rollback", action="store_true", help="指定されたプロファイルのスキルをバックアップから復元する")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    target_profiles = args.profiles or SYSTEM_PROFILES

    if args.rollback:
        logger.info("Executing rollback on target profiles...")
        for prof in target_profiles:
            prof_dir = get_profile_dir(prof)
            skill_file = prof_dir / TARGET_SKILL_REL
            if skill_file.exists():
                restore_backup(skill_file)
        sys.exit(0)

    evidence_p = Path(args.evidence) if args.evidence else None
    res = sync_all_profiles(
        evidence_path=evidence_p,
        raw_lessons_text=args.text,
        profiles=target_profiles,
        dry_run=args.dry_run,
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
