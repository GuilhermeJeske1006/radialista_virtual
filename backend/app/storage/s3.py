from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from .base import Storage


@lru_cache(maxsize=4)
def _cliente(region: str, endpoint_url: str | None):
    # Credenciais nao passam por aqui de proposito: o boto3 ja resolve sozinho via
    # AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, ~/.aws/credentials ou IAM role da instancia/task.
    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url)


class S3Storage(Storage):
    def __init__(self, bucket: str, region: str, endpoint_url: str | None = None):
        if not bucket:
            raise ValueError("aws_s3_bucket precisa estar configurado quando storage_backend=s3")
        self._bucket = bucket
        self._client = _cliente(region, endpoint_url)

    def save(self, path: str, content: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=path, Body=content)

    def read(self, path: str) -> bytes | None:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=path)
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code")
            if codigo in ("NoSuchKey", "404"):
                return None
            raise
        return obj["Body"].read()

    def delete(self, path: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=path)
