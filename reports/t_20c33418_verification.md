# verification_evidence for t_20c33418

$ cd /mnt/d/Project2/kensho && python -m pytest tests/test_done_guard_evidence_binding.py -v
tests/test_done_guard_evidence_binding.py::test_load_candidates_finds_evidence_json PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_finds_evidence_md PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_unrelated_files PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_other_task_files PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_no_verification PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_no_task_id PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_other_task_id PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_no_verification_heading PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_other_task_id_in_heading PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_no_command_citations PASSED
tests/test_done_guard_evidence_binding.py::test_load_candidates_skips_no_evidence_file PASSED
============================== 11 passed in 0.05s ==============================

