"""Pack MCPB bundle for Smithery publication."""
import os
import json
import zipfile
import fnmatch

ROOT = "/mnt/d/Project2/kensho/mcp/kensho-kclub"
MANIFEST = os.path.join(ROOT, "manifest.json")

# Patterns to ignore (same as .mcpbignore)
IGNORE_PATTERNS = [
    ".git",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "tests/",
    "*.md",
    "*.txt",
    "dist/",
    "*.egg-info/",
]

def load_ignore(root):
    """Load ignore patterns from .mcpbignore file."""
    patterns = []
    if os.path.exists(os.path.join(root, ".mcpbignore")):
        with open(os.path.join(root, ".mcpbignore"), "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line.rstrip("/"))
    return patterns

def ignored(rel, is_dir, patterns):
    """Check if a path should be ignored."""
    rel = rel.replace(os.sep, "/")
    for p in patterns:
        if rel == p or rel.startswith(p + "/"):
            return True
        if os.path.isdir(rel) and fnmatch.fnmatch(rel, p + "/") or \
           fnmatch.fnmatch(os.path.basename(rel), p):
            return True
    return False

def main():
    manifest_path = os.path.join(ROOT, "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    
    # Collect files to include (exclude ignored ones)
    entries = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirpath = os.path.relpath(dirpath, ROOT)
        # Filter dirnames in-place to prevent descending into ignored dirs
        dirnames[:] = [d for d in dirnames if not ignored(dirpath, True, IGNORE_PATTERNS)]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if ignored(fpath, False, IGNORE_PATTERNS):
                continue
            entries.append(fpath)
    
    # Sort entries
    entries.sort()
    
    # Create the .mcpb bundle
    output_path = os.path.join(ROOT, "server.mcpb")
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in entries:
            z.write(os.path.join(ROOT, rel), rel)
    
    size = os.path.getsize(output_path)
    print(f"Created {output_path} ({size/1024:.1f} KB)")
    print(f"Total files: {len(entries)}")

if __name__ == "__main__":
    main()
