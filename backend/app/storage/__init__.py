from app.config.settings import settings

from .base import Storage
from .local import LocalStorage

__all__ = ["Storage", "get_storage"]


def get_storage() -> Storage:
    if settings.storage_backend == "s3":
        from .s3 import S3Storage

        return S3Storage(
            bucket=settings.aws_s3_bucket,
            region=settings.aws_region,
            endpoint_url=settings.aws_s3_endpoint_url or None,
        )
    return LocalStorage(settings.upload_dir)
