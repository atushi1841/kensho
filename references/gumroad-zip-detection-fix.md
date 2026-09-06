# Gumroad ZIP Detection Fix (Relative Path Resolution)

## Problem
When checking if a Gumroad product's ZIP file exists using `bundle_info.json`, the `zip` field contains a **relative path** (e.g., `japan-hobby-dataset-20260901.zip`). Using `os.path.exists("relative_path")` directly fails because it searches from the current working directory, not the directory containing `bundle_info.json`.

## Root Cause
In `scripts/kensho_revenue_collect.py` (lines 242-244), the code used:
```python
"zip_exists": os.path.exists(bundle.get("zip", "")),
```
This assumes the path is absolute, but it's actually relative to `bundle_info.json`'s location.

## Solution
Resolve the relative path against `bundle_info.json`'s directory before checking existence:

```python
# bundle_info.json の zip は相対パスのため bundle のあるディレクトリ基準で解決する
zip_path = bundle.get("zip", "")
if zip_path and not os.path.isabs(zip_path):
    zip_path = os.path.join(os.path.dirname(GUMROAD_BUNDLE), zip_path)
result["products"] = 1
result["details"].append({
    "title": bundle.get("title", "?"),
    "price": bundle.get("price", "?"),
    "zip_exists": bool(zip_path) and os.path.exists(zip_path),
    "zip_size": os.path.getsize(zip_path) if zip_path and os.path.exists(zip_path) else 0,
})
```

## Why This Matters
Without this fix, Gumroad product ZIP files appear as "not found" in revenue reports even though they exist, causing false alarms in automation monitoring and incorrect status reporting.

## Location in Codebase
- **File:** `scripts/kensho_revenue_collect.py`
- **Lines:** ~242-244
- **Context:** Inside `collect_gumroad()` function, after loading `bundle_info.json`
