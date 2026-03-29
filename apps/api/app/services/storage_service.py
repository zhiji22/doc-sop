"""
对象存储服务（MinIO / S3 兼容）
封装文件上传和下载操作。MinIO 是自托管的 S3 兼容存储，通过 boto3 客户端访问。
"""
import boto3
from botocore.config import Config
from app.core.config import settings

# boto3 客户端配置：设置连接和读取超时，防止 MinIO 不可用时无限阻塞
_s3_config = Config(
    connect_timeout=5,    # 连接超时 5 秒
    read_timeout=10,      # 读取超时 10 秒
    retries={"max_attempts": 2},
)


def get_s3_client():
    """创建并返回一个 S3 客户端实例，指向本地 MinIO 服务"""
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT,     # MinIO 地址，如 http://localhost:9000
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
        config=_s3_config,
    )


def generate_upload_url(storage_key: str, content_type: str) -> str:
    """
    生成预签名上传 URL（PUT 方式）。
    前端拿到这个 URL 后，直接 PUT 文件到 MinIO，不经过后端中转，节省带宽。
    URL 有效期 600 秒（10 分钟）。
    """
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
    """从 MinIO 下载文件，返回原始字节，用于后续文档解析"""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
    return obj["Body"].read()