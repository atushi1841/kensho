import json
import pytest
from pathlib import Path
from scripts.qa_prompt_sync import (
    load_evidence_lessons,
    extract_lessons_from_text,
    format_lesson_entry,
    apply_lessons_to_skill,
    sync_all_profiles,
    LESSONS_SECTION_HEADER,
)


def test_extract_lessons_from_text():
    text = """
- 教訓1: パイプラインの入力検証を厳格化
* 教訓2: リトライ上限を3回に設定
1. 教訓3: 重複適用をチェック
    """
    lessons = extract_lessons_from_text(text, source_tag="test")
    assert len(lessons) == 3
    assert lessons[0]["text"] == "教訓1: パイプラインの入力検証を厳格化"
    assert lessons[1]["text"] == "教訓2: リトライ上限を3回に設定"
    assert lessons[2]["text"] == "教訓3: 重複適用をチェック"


def test_format_lesson_entry():
    lesson = {"text": "重複防止ロジックの動作テスト", "source": "t_ceb1faef_evidence.json"}
    formatted = format_lesson_entry(lesson)
    assert "[前回教訓]" in formatted
    assert "重複防止ロジックの動作テスト" in formatted
    assert "t_ceb1faef_evidence.json" in formatted


def test_load_evidence_lessons(tmp_path):
    evidence_file = tmp_path / "test_evidence.json"
    data = {
        "lessons": [
            "QA完了時のチェックポイント自動記録",
            {"text": "ロールバック機能の動作確認"}
        ],
        "outcome": {
            "metric": "リードタイム",
            "before": "10分",
            "after": "1分"
        }
    }
    evidence_file.write_text(json.dumps(data), encoding="utf-8")

    lessons = load_evidence_lessons(evidence_file)
    assert len(lessons) == 2
    assert lessons[0]["text"] == "QA完了時のチェックポイント自動記録"
    assert lessons[1]["text"] == "ロールバック機能の動作確認"


def test_apply_lessons_to_skill_dedup_and_rollback(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# AI Team Improvement\n\n既存スキル内容\n", encoding="utf-8")

    lessons = [{"text": "初回テスト教訓", "source": "test_src"}]

    # 1st apply
    changed, applied = apply_lessons_to_skill(skill_file, lessons)
    assert changed is True
    assert len(applied) == 1
    content = skill_file.read_text(encoding="utf-8")
    assert LESSONS_SECTION_HEADER in content
    assert "初回テスト教訓" in content

    # 2nd apply (dedup check)
    changed2, applied2 = apply_lessons_to_skill(skill_file, lessons)
    assert changed2 is False
    assert len(applied2) == 0

    # Backup verify
    backup_file = tmp_path / ".qa_prompt_sync_backups" / "SKILL.md.bak"
    assert backup_file.exists()
    assert "初回テスト教訓" not in backup_file.read_text(encoding="utf-8")
