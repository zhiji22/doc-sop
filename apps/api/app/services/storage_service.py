import boto3
from app.core.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
    )


def generate_upload_url(storage_key: str, content_type: str):
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.STORAGE_BUCKET,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=600,
    )


def download_file_bytes(storage_key: str) -> bytes:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
    return obj["Body"].read()