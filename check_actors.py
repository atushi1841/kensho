#!/usr/bin/env python3
import json
gt = json.load(open('/mnt/d/Project2/kensho/reports/apify-seo/apify-groundtruth-2026-09-06.json'))
for r in gt['public']:
    if r['name'] in ['ai-model-price-api', 'japan-jma-weather', 'japan-mhlw-medical', 'japan-prize-giveaway-scraper']:
        print(r['name'], r['actor_id'])