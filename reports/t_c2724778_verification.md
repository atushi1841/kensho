# Verification Evidence for t_c2724778

## verification_evidence

$ python3 -m pytest tests/test_regression_gates.py::test_gate_skill_md_ratchet -q
tests/test_regression_gates.py .                                         [100%]
1 passed in 1.32s

$ python3 scripts/regression_gates_ledger.py
{"gates": {"skill_md_oversize": {"value": 58, "limit": 0, "detail": "SKILL.md > 20KB: 58 files, e.g. ['.hermes/profiles/kensho-critic/skills/social-media/x-bot-detection/SKILL.md', '.hermes/profiles/kensho-critic/skills/software-development/apify-actor-deployment/SKILL.md', '.hermes/profiles/kensho-critic/skills/software-development/apify-marketplace-scrapers/SKILL.md']"}}}

$ ls -l /home/atushi/.hermes/profiles/kensho-sweeps/skills/autonomous-ai-agents/aider/SKILL.md /home/atushi/.hermes/profiles/kensho-sweeps/skills/autonomous-ai-agents/hermes-cost-optimization/SKILL.md
-rw------- 1 atushi atushi  7619 Sep 21 18:31 /home/atushi/.hermes/profiles/kensho-sweeps/skills/autonomous-ai-agents/aider/SKILL.md
-rw-rw-r-- 1 atushi atushi 15246 Sep 21 18:31 /home/atushi/.hermes/profiles/kensho-sweeps/skills/autonomous-ai-agents/hermes-cost-optimization/SKILL.md
