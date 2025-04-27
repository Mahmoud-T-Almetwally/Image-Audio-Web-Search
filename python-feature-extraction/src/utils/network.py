import requests
from typing import List, Optional
import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


REQUESTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def filter_urls_by_headers(
    urls: List[str],
    media_type: str,
    max_size_bytes: Optional[int] = None,
    timeout: int = 5,
) -> List[str]:
    """
    Filters a list of URLs based on HTTP HEAD request headers.

    Args:
        urls: List of URLs to filter.
        media_type: Expected media type ('image' or 'audio').
        max_size_bytes: Maximum allowed content size in bytes. If None, size is not checked.
        timeout: Timeout in seconds for the HEAD request.

    Returns:
        A list of URLs that passed the checks.
    """
    valid_urls = []
    if not media_type in ["image", "audio"]:
        logger.error(
            f"Invalid media_type specified: {media_type}. Must be 'image' or 'audio'."
        )
        return []

    expected_content_prefix = f"{media_type}/"

    for url in urls:
        try:
            response = requests.head(
                url, headers=REQUESTS_HEADERS, timeout=timeout, allow_redirects=True
            )

            if not response.ok:
                logger.warning(f"Skipping URL (Status {response.status_code}): {url}")
                continue

            headers = response.headers

            content_type = headers.get("Content-Type")
            if not content_type:
                logger.warning(f"Skipping URL (Missing Content-Type): {url}")
                continue
            if not content_type.lower().startswith(expected_content_prefix):
                logger.warning(
                    f"Skipping URL (Wrong Content-Type: {content_type}): {url}"
                )
                continue

            if max_size_bytes is not None:
                content_length_str = headers.get("Content-Length")
                if not content_length_str:

                    logger.warning(
                        f"Allowing URL (Missing Content-Length, size check skipped): {url}"
                    )
                else:
                    try:
                        content_length = int(content_length_str)
                        if content_length > max_size_bytes:
                            logger.warning(
                                f"Skipping URL (Exceeds max size {max_size_bytes} bytes: {content_length} bytes): {url}"
                            )
                            continue
                    except ValueError:
                        logger.warning(
                            f"Skipping URL (Invalid Content-Length: {content_length_str}): {url}"
                        )
                        continue

            valid_urls.append(url)

        except requests.exceptions.Timeout:
            logger.warning(f"Skipping URL (HEAD request timed out): {url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Skipping URL (HEAD request failed: {e}): {url}")
        except Exception as e:
            logger.error(f"Unexpected error during HEAD request for {url}: {e}")

    logger.info(f"Filtered URLs: {len(valid_urls)} out of {len(urls)} passed checks.")
    return valid_urls


if __name__ == "__main__":
    test_urls = [
        "https://images.pexels.com/photos/20787/pexels-photo.jpg?auto=compress&cs=tinysrgb&dpr=1&w=500",
        "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
        "http://inv.alid.url/image.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Dialog-error.svg/2048px-Dialog-error.svg.png",
        "https://raw.githubusercontent.com/pytorch/pytorch/main/README.md",
        "https://github.com/karolpiczak/ESC-50/raw/master/audio/1-100032-A-0.wav",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    ]

    print("\n--- Filtering for Images (Max 10MB) ---")
    valid_image_urls = filter_urls_by_headers(
        test_urls, "image", max_size_bytes=10 * 1024 * 1024
    )
    print("Valid Image URLs:", valid_image_urls)

    print("\n--- Filtering for Audio (Max 50MB) ---")
    valid_audio_urls = filter_urls_by_headers(
        test_urls, "audio", max_size_bytes=50 * 1024 * 1024
    )
    print("Valid Audio URLs:", valid_audio_urls)
