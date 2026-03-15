import time
import logging
import os
import random
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def get_s3_client():
    from botocore.config import Config
    
    endpoint_url = os.getenv('SUPABASE_URL')
    
    # Configure signature version for generic S3 compatibility (like Supabase/R2)
    my_config = Config(
        signature_version='s3v4',
    )
    
    kwargs = {
        'service_name': 's3',
        'aws_access_key_id': os.getenv('SUPABASE_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('SUPABASE_SECRET_ACCESS_KEY'),
        'region_name': os.getenv('SUPABASE_REGION', 'us-east-1'),
        'config': my_config
    }
    
    if endpoint_url:
        kwargs['endpoint_url'] = endpoint_url
        
    return boto3.client(**kwargs)

def upload_to_s3(file_obj, bucket, object_name, content_type=None):
    """Upload a file to an S3 bucket"""
    s3_client = get_s3_client()
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
        
    try:
        s3_client.upload_fileobj(file_obj, bucket, object_name, ExtraArgs=extra_args)
    except ClientError as e:
        logger.error(e)
        return False
    return True

def generate_presigned_url(bucket, object_name, expiration=3600, response_content_type=None):
    """Generate a presigned URL to share an S3 object"""
    s3_client = get_s3_client()
    try:
        params = {'Bucket': bucket, 'Key': object_name}
        if response_content_type:
            params['ResponseContentType'] = response_content_type
            
        response = s3_client.generate_presigned_url('get_object',
                                                    Params=params,
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logger.error(e)
        return None
    return response

def download_from_s3(bucket, object_name, file_name):
    """Download a file from S3"""
    s3_client = get_s3_client()
    try:
        s3_client.download_file(bucket, object_name, file_name)
    except ClientError as e:
        logger.error(e)
        return False
    return True

def generate_with_retry(client, model_name, content, retries=3, initial_delay=1, **kwargs):
    """
    Generates content using the Gemini model with retry logic for rate limits (429).
    """
    delay = initial_delay
    from google.genai.errors import APIError
    
    for attempt in range(retries + 1):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=content,
                **kwargs
            )
        except APIError as e:
            # Check for 429 Rate Limit
            if e.code == 429 and attempt < retries:
                sleep_time = delay + random.uniform(0, 1)
                logger.warning(f"Rate limit hit ({e.message}). Retrying in {sleep_time:.2f}s (Attempt {attempt+1}/{retries})")
                time.sleep(sleep_time)
                delay *= 2 # Exponential backoff
            else:
                raise e
        except Exception as e:
             raise e

def download_youtube_video(url, output_path):
    """
    Downloads a YouTube video using yt-dlp.
    Returns the filename if successful, None otherwise.
    """
    import yt_dlp
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': False, # Enable output for debugging
        'no_warnings': False,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }
    
    # Check for Proxy
    proxy = os.getenv('YOUTUBE_PROXY')
    if proxy:
        ydl_opts['proxy'] = proxy
        logger.info("Using proxy for YouTube download")

    # Check for Cookies env var to bypass bot detection
    cookies_content = os.getenv('YOUTUBE_COOKIES')
    cookie_file_path = None
    
    if cookies_content:
        try:
            logger.info(f"Found YOUTUBE_COOKIES with length: {len(cookies_content)}")
            if not cookies_content.startswith("# Netscape HTTP Cookie File"):
                logger.warning("Cookies content does not appear to be in Netscape format! It should start with '# Netscape HTTP Cookie File'")

            import tempfile
            # Create a temp file for cookies
            fd, cookie_file_path = tempfile.mkstemp(suffix='.txt', text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(cookies_content)
            ydl_opts['cookiefile'] = cookie_file_path
            logger.info(f"Created temporary cookie file at {cookie_file_path}")
        except Exception as e:
            logger.error(f"Failed to create cookie file: {e}")

    try:
        logger.info(f"Starting YouTube download for URL: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        logger.info("YouTube download completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        return False
    finally:
        # Cleanup cookie file
        if cookie_file_path and os.path.exists(cookie_file_path):
            try:
                os.remove(cookie_file_path)
                logger.info("Cleaned up temporary cookie file")
            except Exception as e:
                logger.warning(f"Failed to remove cookie file: {e}")
