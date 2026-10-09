#!/usr/bin/env python3
"""
Proxy dead compensation manager.
When kudou and zin20120731 are dead_proxy, temporarily raise
atushi16 and TankanNotes batch max to compensate daily target.
Idempotent and auto-revert on recovery.
"""
from __future__ import annotations
import json
from pathlib import Path
import yaml

PROJECT = Path('/mnt/d/Project2/kensho')
CONFIG_PATH = PROJECT / 'config.yaml'
STATUS_DIR = PROJECT / 'data' / 'status'
STATE_FILE = PROJECT / 'data' / 'compensation_state.json'

DEAD_ACCOUNTS = ['kudou', 'zin20120731']
TARGETS = {
    'atushi16': 10,      # 7+3
    'TankanNotes': 18,   # 15+3
}
ORIGINALS = {
    'atushi16': 7,
    'TankanNotes': 15,
}

def is_dead(account: str) -> bool:
    p = STATUS_DIR / f'{account}.json'
    if not p.exists():
        return False
    try:
        s = json.loads(p.read_text(encoding='utf-8'))
        return s.get('status') == 'dead_proxy'
    except Exception:
        return False

def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8'))

def save_config(cfg: dict):
    CONFIG_PATH.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')

def current_batch_max(cfg: dict, key: str) -> list[int]:
    for a in cfg.get('accounts', []):
        if a.get('key') == key:
            return [b.get('max') for b in a.get('schedule', {}).get('batches', [])]
    return []

def apply_compensation(cfg: dict) -> bool:
    changed = False
    for key, target_max in TARGETS.items():
        for a in cfg.get('accounts', []):
            if a.get('key') != key:
                continue
            batches = a.get('schedule', {}).get('batches', [])
            if not isinstance(batches, list):
                continue
            for b in batches:
                if b.get('max') != target_max:
                    b['max'] = target_max
                    changed = True
    return changed

def revert_compensation(cfg: dict) -> bool:
    changed = False
    for key, orig_max in ORIGINALS.items():
        for a in cfg.get('accounts', []):
            if a.get('key') != key:
                continue
            batches = a.get('schedule', {}).get('batches', [])
            for b in batches:
                if b.get('max') != orig_max:
                    b['max'] = orig_max
                    changed = True
    return changed

def verify_limits(cfg: dict) -> bool:
    # simple check: max per batch <=20 and daily target within allowed
    ok = True
    for key in TARGETS:
        for a in cfg.get('accounts', []):
            if a.get('key') != key:
                continue
            for b in a.get('schedule', {}).get('batches', []):
                if b.get('max', 0) > 20:
                    ok = False
    return ok

def main():
    dead = [a for a in DEAD_ACCOUNTS if is_dead(a)]
    both_dead = set(dead) >= set(DEAD_ACCOUNTS)
    cfg = load_config()
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            state = {}

    active = state.get('active', False)

    if both_dead:
        # apply compensation if not already active or values differ
        need = False
        for key, target in TARGETS.items():
            cur = current_batch_max(cfg, key)
            if not cur or any(v != target for v in cur):
                need = True
        if need:
            # save snapshot if not present
            if not active:
                snapshot = {}
                for key in TARGETS:
                    snapshot[key] = current_batch_max(cfg, key)
                state = {
                    'active': True,
                    'snapshot': snapshot,
                    'applied_at': __import__('datetime').datetime.utcnow().isoformat(),
                }
            changed = apply_compensation(cfg)
            if verify_limits(cfg):
                save_config(cfg)
                STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
                print('Compensation applied')
            else:
                print('Compensation aborted: limits exceeded')
        else:
            print('Compensation already active')
    else:
        # revert if active
        if active:
            changed = revert_compensation(cfg)
            if changed:
                save_config(cfg)
                if STATE_FILE.exists():
                    STATE_FILE.unlink()
                print('Compensation reverted')
            else:
                print('Compensation already reverted')
        else:
            print('No compensation needed')

if __name__ == '__main__':
    main()
