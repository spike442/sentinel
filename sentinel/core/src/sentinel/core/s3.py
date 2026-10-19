import boto3
from botocore.config import Config
from sentinel.core.config.settings import S3ServiceConfig


def s3_client(config: S3ServiceConfig, access_key_id: str, secret_access_key: str):
    addressing = Config(s3={"addressing_style": "path"})
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        region_name=config.region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=addressing,
    )
