from unittest.mock import patch, MagicMock
from config import TranslationConfig


def _cfg(**kwargs):
    defaults = dict(url="http://localhost:5000", source_lang="en", target_lang="es")
    return TranslationConfig(**{**defaults, **kwargs})


def test_translate_returns_translated_text():
    from translator import translate
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"translatedText": "Hola mundo"}
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = translate("Hello world", _cfg())
    assert result == "Hola mundo"
    mock_post.assert_called_once_with(
        "http://localhost:5000/translate",
        json={"q": "Hello world", "source": "en", "target": "es", "format": "text"},
        timeout=5.0,
    )


def test_translate_returns_none_on_network_error():
    from translator import translate
    with patch("requests.post", side_effect=ConnectionError("down")):
        result = translate("Hello", _cfg())
    assert result is None


def test_translate_returns_none_on_bad_response():
    from translator import translate
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500")
    with patch("requests.post", return_value=mock_resp):
        result = translate("Hello", _cfg())
    assert result is None


def test_translate_returns_none_on_missing_key():
    from translator import translate
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"unexpected": "key"}
    with patch("requests.post", return_value=mock_resp):
        result = translate("Hello", _cfg())
    assert result is None
