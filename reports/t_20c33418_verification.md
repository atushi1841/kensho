## verification_evidence for t_20c33418

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_20c33418 --workdir /mnt/d/Project2/kensho --write-evidence --payload-file /tmp/payload.json
written: /mnt/d/Project2/kensho/reports/t_20c33418_evidence.json (guard j verification => pass, sha256=4904e1525df2306b41a5ea683b6d85e7e8f542b0afa48b2201beea3274065513)
$ git add reports/t_20c33418_evidence.json reports/t_20c33418_verification.md
$ git commit -m "t_20c33418: implement bind check with sibling commit support and evidence durability"
$ git push origin main
$ python3 -m pytest tests/test_done_guard_evidence_binding.py -v
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