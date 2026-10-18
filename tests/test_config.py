from swarmlab.config import Settings


def test_tls_is_boolean_and_secrets_are_not_public(monkeypatch, tmp_path):
    monkeypatch.setenv("FALKORDB_TLS", "false")
    monkeypatch.setenv("FALKORDB_PASSWORD", "test-password")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    settings = Settings.load(tmp_path / "missing.env")
    assert settings.tls is False
    assert "test-password" not in repr(settings)
    assert "test-key" not in str(settings.public_status())
    monkeypatch.setenv("FALKORDB_TLS", "true")
    assert Settings.load(tmp_path / "missing.env").tls is True
