#!/usr/bin/env python3
"""v26-1 候補5API の現在のプラン単価を表示（読み取り専用）。

rapidapi_pricing_set.py の関数を再利用して、候補API の BASIC/PRO/ULTRA 単価を確認する。
認証は goo-net-car-scraper/rapidapi_auth.json を再利用。
"""
import json
import sys

sys.path.insert(0, "/mnt/d/Project2/kensho/scripts")
# 副作用（main内の argparse）を出さないため、関数のみ import
import rapidapi_pricing_set as rps

# v26 候補: 各カテゴリの旗艦（言語サフィックスなし・PUBLIC) 5本
CANDIDATES = {
    "japan-kakaku": "api_45bf102f-6d1b-4fd5-9179-f164de167ffd",
    "japan-rent": "api_2e8e063d-f2a3-43de-9fe4-50d5eb16659a",
    "japan-watch": "api_cb7a9d01-e8db-4f0d-b91f-031899d5e7cc",
    "japan-luxury": "api_8941b445-afab-4f21-abbe-a58e96b21325",
    "japan-instrument": "api_8ccef00b-e8be-44b2-b4e4-3c96fdaf7481",
}


def main():
    auth = rps._load_auth()
    for key, api_id in CANDIDATES.items():
        info = rps.fetch_api_info(auth, api_id)
        versions = rps.fetch_plan_versions(auth, api_id)
        print(f"== {key}  ({info['name']})  vis={info.get('visibility')}")
        for v in versions:
            price = rps.per_call_price(v)
            tier = v["plan_name"]
            print(f"   {tier:<6} price=${price} ver={v['version_id'][:30]}... status={v['status']}")
        if not versions:
            print("   (tier なし → 完全無料・課金未設定)")


if __name__ == "__main__":
    main()
