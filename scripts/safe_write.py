#!/usr/bin/env python3
"""Safe file writer with CAS and claim protection."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path


class SafeWriter:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.claims_file = self.data_dir / "edit_claims.json"

    def _get_file_hash(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except FileNotFoundError:
            return None

    def _load_claims(self):
        if self.claims_file.exists():
            with open(self.claims_file, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return []

    def _save_claims(self, claims):
        temp_file = self.claims_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(claims, f, indent=2)
        os.replace(temp_file, self.claims_file)

    def _is_claim_stale(self, claim, ttl=3600):
        if time.time() - claim['timestamp'] > ttl:
            return True
        try:
            import psutil
            for proc in psutil.process_iter(['pid']):
                if proc.info['pid'] == int(claim['pid']):
                    return False
            return True
        except (ImportError, ValueError, RuntimeError):
            return True

    def _prune_stale_claims(self):
        claims = self._load_claims()
        original_length = len(claims)
        claims = [c for c in claims if not self._is_claim_stale(c)]
        if len(claims) < original_length:
            self._save_claims(claims)
        return original_length - len(claims)

    def write(self, path, expected_hash, from_file=None, stdin=False):
            file_path = Path(path)
        
            # Read content FIRST (before hash check)
            if from_file:
                with open(from_file, 'rb') as f:
                    content = f.read()
            elif stdin:
                content = sys.stdin.buffer.read()
            else:
                print("ERROR: Must specify --from-file or --stdin", file=sys.stderr)
                sys.exit(1)
        
            # Get current hash of the target file
            current_hash = self._get_file_hash(file_path)
        
            # Verify hash matches expected
            if current_hash != expected_hash:
                if current_hash is None:
                    print(f"ERROR: File '{path}' does not exist", file=sys.stderr)
                else:
                    print(f"CONFLICT: current={current_hash}, expected={expected_hash}", file=sys.stderr)
                sys.exit(3)
        
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            temp_file = file_path.with_suffix(file_path.suffix + '.tmp')
            try:
                # Write to temp file
                with open(temp_file, 'wb') as f:
                    f.write(content)
            
                # Atomic replace
                os.replace(temp_file, file_path)
            
                # Sync to disk
                with open(file_path, 'rb') as f:
                    f.read()
            
                print(f"SUCCESS: Written to '{path}'")
                sys.exit(0)
        
            except Exception as e:
                # Clean up temp file if it exists
                if temp_file.exists():
                    temp_file.unlink()
                print(f"ERROR: Failed to write '{path}': {e}", file=sys.stderr)
                sys.exit(5)

    def read(self, path):
        file_path = Path(path)

        if not file_path.exists():
            result = {'sha256': None, 'lines': 0}
            print(json.dumps(result))
            sys.exit(0)

        # Get hash
        file_hash = self._get_file_hash(file_path)

        # Get line count
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = sum(1 for _ in f)
        except Exception:
            lines = 0

        result = {'sha256': file_hash, 'lines': lines}
        print(json.dumps(result))
        sys.exit(0)

    def claim(self, path, task_id, ttl=3600):
        file_path = Path(path)

        # Check if file is already claimed (non-stale)
        claims = self._load_claims()
        self._prune_stale_claims()
        claims = self._load_claims()

        for claim in claims:
            if claim['path'] == str(file_path) and not self._is_claim_stale(claim, ttl):
                print(f"ERROR: Editing in progress: {claim['task_id']}", file=sys.stderr)
                sys.exit(4)

        import os as _os_mod
        claims.append({
            'path': str(file_path),
            'task_id': task_id,
            'pid': str(_os_mod.getpid()),
            'timestamp': time.time()
        })
        self._save_claims(claims)
        print(f"Claim added for '{path}' by {task_id}")
        sys.exit(0)

    def release(self, path, task_id):
        file_path = Path(path)
        claims = self._load_claims()
        new_claims = [c for c in claims if not (c['path'] == str(file_path) and c['task_id'] == task_id)]
        if len(new_claims) < len(claims):
            self._save_claims(new_claims)
            print(f"Released '{path}' from {task_id}")
            sys.exit(0)
        else:
            print(f"ERROR: No claim found", file=sys.stderr)
            sys.exit(7)

    def claims(self, json_output=False):
        pruned = self._prune_stale_claims()
        claims = self._load_claims()

        if json_output:
            print(json.dumps(claims))
        else:
            print(f"Claims: {len(claims)} (pruned {pruned})")
            for c in claims:
                print(f"  {c['path']} -> {c['task_id']}")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description='Safe file writing with CAS')
    parser.add_argument('--data-dir', type=str, default='data',
                        help='Directory for claims data (default: ./data)')
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--path', type=str)
    parser.add_argument('--expect-sha256', type=str)
    parser.add_argument('--from-file', type=str)
    parser.add_argument('--stdin', action='store_true')
    parser.add_argument('--read', action='store_true')
    parser.add_argument('--claim', action='store_true')
    parser.add_argument('--task', type=str)
    parser.add_argument('--claims', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--ttl', type=int, default=3600)

    args = parser.parse_args()
    w = SafeWriter(data_dir=args.data_dir)

    if args.write:
        w.write(args.path, args.expect_sha256, args.from_file, args.stdin)
    elif args.read:
        w.read(args.path)
    elif args.claim:
        w.claim(args.path, args.task, args.ttl)
    elif args.claims:
        w.claims(args.json)
    elif args.release:
        w.release(args.path, args.task)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()