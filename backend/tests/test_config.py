import pytest
from pydantic import ValidationError

from src.core.config import Settings


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_PASSWORD=file-password\nPOSTGRES_HOST=file-host\n")
    monkeypatch.setenv("POSTGRES_HOST", "environment-host")
    settings = Settings(_env_file=env_file)
    assert settings.postgres_host == "environment-host"
    assert settings.postgres_password.get_secret_value() == "file-password"


@pytest.mark.parametrize("password", [None, ""])
def test_missing_or_empty_password_is_rejected(password):
    values = {} if password is None else {"postgres_password": password}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize("port", [0, 65536])
def test_invalid_port_is_rejected(port):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, postgres_password="test-password", postgres_port=port)


def test_password_special_characters_are_preserved_and_masked():
    password = "p@ss:/?#%word"
    settings = Settings(_env_file=None, postgres_password=password)
    assert settings.database_url.password == password
    assert password not in repr(settings)
    assert password not in str(settings.database_url)
