from camp_match.config.settings import Settings
import pytest


def test_settings_defaults():
    settings = Settings()
    assert settings.app_name == "Camp Match API"
    assert settings.app_env == "local"
    assert settings.debug is False
    assert settings.log_level == "INFO"
    assert settings.messaging_max_message_length == 2000
    assert settings.messaging_history_default_limit == 30
    assert settings.messaging_history_max_limit == 100
    assert settings.messaging_send_rate_limit == 30
    assert settings.messaging_send_rate_window_seconds == 60
    assert settings.messaging_create_rate_limit == 10
    assert settings.messaging_create_rate_window_seconds == 60
    assert settings.messaging_ws_auth_ttl_seconds == 900
    assert settings.messaging_realtime_backend == "in_memory"


def test_settings_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    settings = Settings()
    assert settings.app_env == "test"


def test_invalid_messaging_realtime_backend(monkeypatch):
    monkeypatch.setenv("MESSAGING_REALTIME_BACKEND", "invalid_backend")
    with pytest.raises(Exception):
        Settings()
