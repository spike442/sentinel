import os

CREDENTIALS_PROVIDER = "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"


def s3a_options(s3: dict) -> dict[str, str]:
    secure = s3["endpoint"].startswith("https://")
    return {
        "spark.hadoop.fs.s3a.endpoint": s3["endpoint"],
        "spark.hadoop.fs.s3a.endpoint.region": s3["region"],
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": str(secure).lower(),
        "spark.hadoop.fs.s3a.aws.credentials.provider": CREDENTIALS_PROVIDER,
        "spark.hadoop.fs.s3a.access.key": os.environ["S3_ACCESS_KEY_ID"],
        "spark.hadoop.fs.s3a.secret.key": os.environ["S3_SECRET_ACCESS_KEY"],
    }
