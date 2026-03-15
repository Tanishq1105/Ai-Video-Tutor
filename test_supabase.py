import os
from dotenv import load_dotenv

load_dotenv()

from backend.utils import get_s3_client

s3_client = get_s3_client()
bucket_name = os.getenv('SUPABASE_BUCKET_NAME')

try:
    print(f"Attempting to connect to bucket: {bucket_name}")
    response = s3_client.list_objects_v2(Bucket=bucket_name)
    
    print("\n✅ Connection Successful!")
    if 'Contents' in response:
        print(f"Found {len(response['Contents'])} files:")
        for obj in response['Contents']:
            print(f" - {obj['Key']} ({obj['Size']} bytes)")
    else:
        print("Bucket is currently empty.")
except Exception as e:
    print("\n❌ Connection Failed!")
    print(f"Error: {e}")
