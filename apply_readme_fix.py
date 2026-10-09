#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()
HF_TOKEN = os.environ.get("HF_TOKEN")
HF_REPO = "saboten1/japan-hobby-collectibles-prices-sample"

api = HfApi(token=HF_TOKEN)

# Upload correct README
readme_path = "/mnt/d/Project2/kensho/dataset_readme.md"
api.upload_file(
    path_or_fileobj=readme_path,
    path_in_repo="README.md",
    repo_id=HF_REPO,
    repo_type="dataset",
)
print("README updated")

# Also ensure CSV exists
api.upload_file(
    path_or_fileobj="/mnt/d/Project2/kensho/data/anime_figure_prices_normalized.csv",
    path_in_repo="data/normalized_prices.csv",
    repo_id=HF_REPO,
    repo_type="dataset",
)
print("CSV uploaded")

r = api.dataset_info(HF_REPO)
print(f"id={r.id} downloads={r.downloads} likes={r.likes}")
