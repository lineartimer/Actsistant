import httpx
from pathlib import Path
import structlog


# The EUR-Lex website blocks scripted clients, so the official XHTML of the Act
# (Regulation (EU) 2024/1689) is fetched from the Publications Office's Cellar API
EU_AI_ACT_URL = "https://publications.europa.eu/resource/celex/32024R1689"

# The downloaded Act is kept next to this file
EU_AI_ACT_PATH = Path(__file__).with_name("eu_ai_act.xhtml")


_logger = structlog.get_logger(__name__)


class DownloadError(Exception):
    pass


async def download_act() -> bytes:
    if EU_AI_ACT_PATH.exists():
        _logger.info("EU AI Act loaded from file", path=str(EU_AI_ACT_PATH))
        return EU_AI_ACT_PATH.read_bytes()

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            response = await client.get(
                EU_AI_ACT_URL,
                headers={
                    "Accept": "application/xhtml+xml",
                    "Accept-Language": "eng"
                }
            )

        response.raise_for_status()

    except httpx.HTTPError as e:
        raise DownloadError(f"Failed to download the EU AI Act: {e}") from e

    EU_AI_ACT_PATH.write_bytes(response.content)

    _logger.info("EU AI Act downloaded", url=EU_AI_ACT_URL, bytes=len(response.content))
    return response.content
