## verification_evidence
t_beeb6e26: dev.to username mismatch fix verification

$ grep -r "atushi1841" /mnt/d/Project2/kensho/scripts/ --include="*.py" --include="*.sh" | grep -v "github\|git-credential\|README\|gumroad\|apify.com/fruitful" | wc -l
0
$ curl -s "https://dev.to/api/articles?username=atu_ino_ed473db24d76d234a" | python3 -c "import json,sys;d=json.load(sys.stdin);print(f'articles: {len(d)}')"
articles: 30
$ curl -s "https://dev.to/api/users/by_username?url=atu_ino_ed473db24d76d234a" | python3 -c "import json,sys;d=json.load(sys.stdin);print(f'username={d.get(\\\"username\\\")}')"
username=atu_ino_ed473db24d76d234a
$ grep -r "atu_ino_ed473db24d76d234a" /mnt/d/Project2/kensho/scripts/ --include="*.py" --include="*.sh" | head -5
# No output - scripts already use correct username