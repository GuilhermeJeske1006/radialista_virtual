import boto3
import pytest
from moto import mock_aws

from app.config.settings import settings
from app.storage import get_storage
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


@pytest.fixture(autouse=True)
def _reset_storage_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "aws_s3_bucket", "")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_s3_endpoint_url", "")


def test_get_storage_devolve_local_por_padrao():
    assert isinstance(get_storage(), LocalStorage)


def test_get_storage_devolve_s3_quando_configurado(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "aws_s3_bucket", "meu-bucket")
    with mock_aws():
        assert isinstance(get_storage(), S3Storage)


def test_local_storage_save_read_delete(tmp_path):
    storage = LocalStorage(str(tmp_path))

    storage.save("biblioteca_audio/1/a.mp3", b"conteudo")
    assert storage.read("biblioteca_audio/1/a.mp3") == b"conteudo"

    storage.delete("biblioteca_audio/1/a.mp3")
    assert storage.read("biblioteca_audio/1/a.mp3") is None


def test_local_storage_read_inexistente_devolve_none(tmp_path):
    storage = LocalStorage(str(tmp_path))
    assert storage.read("nao/existe.mp3") is None


def test_local_storage_delete_inexistente_nao_falha(tmp_path):
    LocalStorage(str(tmp_path)).delete("nao/existe.mp3")


@mock_aws
def test_s3_storage_save_read_delete():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="radialista-teste")
    storage = S3Storage(bucket="radialista-teste", region="us-east-1")

    storage.save("patrocinadores/1/a.mp3", b"conteudo")
    assert storage.read("patrocinadores/1/a.mp3") == b"conteudo"

    storage.delete("patrocinadores/1/a.mp3")
    assert storage.read("patrocinadores/1/a.mp3") is None


@mock_aws
def test_s3_storage_read_inexistente_devolve_none():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="radialista-teste")
    storage = S3Storage(bucket="radialista-teste", region="us-east-1")

    assert storage.read("nao/existe.mp3") is None


def test_s3_storage_sem_bucket_levanta_erro():
    with pytest.raises(ValueError):
        S3Storage(bucket="", region="us-east-1")
