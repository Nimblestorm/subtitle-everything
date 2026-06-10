import logging

import requests
from config import TranslationConfig

logger = logging.getLogger(__name__)


def translate(text: str, config: TranslationConfig) -> str | None:
    try:
        response = requests.post(
            f"{config.url}/translate",
            json={
                "q": text,
                "source": config.source_lang,
                "target": config.target_lang,
                "format": "text",
            },
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()["translatedText"]
    except Exception:
        return None
