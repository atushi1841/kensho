#!/usr/bin/env python3
import subprocess
import os
import sys

# Get GH_TOKEN from gh CLI
result = subprocess.run(['cmd.exe', '/c', 'gh auth token'], capture_output=True, text=True)
token = result.stdout.strip()
os.environ['GH_TOKEN'] = token

# Now run the audit script for all 4 actors
sys.argv = ['apify_readme_deploy.py', '--audit', '--only', 'ai-model-price-api,japan-jma-weather,japan-mhlw-medical,japan-prize-giveaway-scraper']
sys.path.insert(0, '/mnt/d/Project2/kensho/scripts')
from apify_readme_deploy import main
main()