# t_0dc05be4 verification

## verification_evidence

- `$ grep -R 'class="source-button stat-card"' scripts/gen_status_html.py` -> satisfied (line 294)
- `$ bash scripts/generate-status.sh` -> DATA_OK + [OK] kensho-status.html
- `$ grep -c 'source-button' kensho-status.html` -> 2 (9 source-button elements each with data-source=)
- `$ grep -c 'filterable-item' kensho-status.html` -> 4
- `$ grep -o 'data-source="[^"]*"' kensho-status.html` -> twscrape/kenshouclub/knshow/chancecom/cpmeikan/kema/kensho-everyday/ken-kaku/unknown all present

## verification_commands

- `$ grep -R 'class="source-button stat-card"' scripts/gen_status_html.py`
- `$ bash scripts/generate-status.sh`
- `$ grep -c 'source-button' kensho-status.html`
- `$ grep -c 'filterable-item' kensho-status.html`
