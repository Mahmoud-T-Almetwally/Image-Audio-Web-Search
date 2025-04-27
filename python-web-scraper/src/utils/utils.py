import logging
from urllib.parse import urlparse, urlunparse
from typing import Optional, List

logger = logging.getLogger(__name__)


def validate_url(url_string: str) -> bool:
    """
    Checks if a string is a valid HTTP/HTTPS URL with a domain.
    """
    if not isinstance(url_string, str) or not url_string:
        return False
    try:
        parsed = urlparse(url_string)

        return bool(parsed.scheme in ["http", "https"] and parsed.netloc)
    except ValueError:

        logger.warning(f"ValueError during URL validation for: {url_string[:100]}...")
        return False


def normalize_url(url_string: str) -> Optional[str]:
    """
    Attempts to normalize a URL string.
    - Ensures http/https scheme (defaults to http if missing).
    - Lowercases scheme and domain.
    - Removes default ports.
    - Removes fragments.
    """
    if not isinstance(url_string, str) or not url_string:
        return None

    if "://" not in url_string:
        logger.debug(f"Assuming http scheme for URL: {url_string}")
        url_string = "http://" + url_string

    try:
        parts = urlparse(url_string)

        if not parts.scheme in ["http", "https"] or not parts.netloc:
            logger.warning(f"Cannot normalize invalid URL structure: {url_string}")
            return None

        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()

        if (scheme == "http" and netloc.endswith(":80")) or (
            scheme == "https" and netloc.endswith(":443")
        ):
            netloc = netloc.rsplit(":", 1)[0]

        normalized = urlunparse(
            (
                scheme,
                netloc,
                parts.path if parts.path else "/",
                parts.params,
                parts.query,
                "",
            )
        )

        return normalized

    except ValueError:
        logger.warning(
            f"ValueError during URL normalization for: {url_string[:100]}..."
        )
        return None


def validate_depth(depth: int) -> bool:
    """Checks if depth is a non-negative integer."""
    return isinstance(depth, int) and depth >= 0


def validate_crawl_strategy(strategy: str, allowed_strategies: List[str]) -> bool:
    """Checks if the strategy is in the allowed list."""
    return isinstance(strategy, str) and strategy in allowed_strategies


def extract_domain(url_string: str) -> Optional[str]:
    """Extracts the network location (domain) from a URL string."""
    if not isinstance(url_string, str) or not url_string:
        return None
    try:
        parsed = urlparse(url_string)

        return parsed.netloc if parsed.scheme in ["http", "https"] else None
    except ValueError:
        logger.warning(
            f"ValueError during domain extraction for: {url_string[:100]}..."
        )
        return None


if __name__ == "__main__":
    test_urls = [
        "http://example.com/path?query=1",
        "https://WWW.Example.COM:443/PaTh/",
        "ftp://example.com",
        "example.com/no_scheme",
        "http://example.com:8080",
        None,
        "",
        "http://",
        "http://example.com",
    ]

    print("--- URL Validation ---")
    for url in test_urls:
        print(f"'{url}' -> Valid: {validate_url(str(url))}")

    print("\n--- URL Normalization ---")
    for url in test_urls:
        print(f"'{url}' -> Normalized: {normalize_url(str(url))}")

    print("\n--- Domain Extraction ---")
    for url in test_urls:
        print(f"'{url}' -> Domain: {extract_domain(str(url))}")

    print("\n--- Parameter Validation ---")
    print(f"Depth 2: {validate_depth(2)}")
    print(f"Depth -1: {validate_depth(-1)}")
    print(f"Depth 'abc': {validate_depth('abc')}")
    strategies = ["default", "pagination_only", "none"]
    print(f"Strategy 'default': {validate_crawl_strategy('default', strategies)}")
    print(f"Strategy 'other': {validate_crawl_strategy('other', strategies)}")
