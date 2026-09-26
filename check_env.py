import os
from dotenv import load_dotenv
load_dotenv()
key = os.environ.get('DEVTO_API_KEY', '')
print(f'DEVTO_API_KEY length: {len(key)}')
print(f'DEVTO_API_KEY value: {key[:10]}...' if len(key) > 10 else f'DEVTO_API_KEY value: {key}')