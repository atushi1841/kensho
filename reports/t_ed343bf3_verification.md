# t_ed343bf3 verification report

## verification_evidence

$ curl -sL --max-time 30 -A "Mozilla/5.0" https://www.skills.sh/ -o skills_sh_investigation/index.html
→ saved to skills_sh_investigation/index.html (938KB)

$ grep -o 'totalSkills[^}]*}' skills_sh_investigation/index.html
→ totalSkills\\\":9828,\\\"allTimeTotal\\\":1379229,\\\"view\\\":\\\"all-time\\\"}

$ curl -sL --max-time 20 -A "Mozilla/5.0" "https://api.github.com/repos/vercel-labs/skills/git/trees/main?recursive=1" 2>/dev/null | grep -o '\"path\": \"[^\"]*\\.md\"' | cut -d'"' -f4 | head -5
→ skills/find-skills/SKILL.md
