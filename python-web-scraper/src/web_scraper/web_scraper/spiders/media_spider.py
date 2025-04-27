import scrapy
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse
import logging


from ..items import MediaItem

logger = logging.getLogger(__name__)


class MediaSpider(scrapy.Spider):
    name = "media"

    IMAGE_EXTENSIONS = [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".bmp",
        ".tiff",
    ]
    AUDIO_EXTENSIONS = [".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"]

    PAGINATION_SELECTORS = [
        'a[rel="next"]::attr(href)',
        'a[aria-label*="Next page"]::attr(href)',
        'a:contains("Next")::attr(href)',
        'a:contains(">")::attr(href)',
        ".pagination a::attr(href)",
        ".pager a::attr(href)",
    ]

    def __init__(
        self,
        *args,
        start_url=None,
        allowed_domains=None,
        depth_limit=2,
        use_playwright=True,
        crawl_strategy="default",
        **kwargs,
    ):
        """
        Initializes the spider.

        Args:
            start_url (str): The initial URL to crawl. Required.
            allowed_domains (str, optional): Comma-separated list of allowed domains.
                                             If None, derived from start_url.
            depth_limit (int, optional): Maximum crawl depth. Defaults to 2.
            use_playwright (bool, optional): Whether to use Playwright for requests. Defaults to True.
            crawl_strategy (str, optional): 'default' (follow all valid links),
                                           'pagination_only' (only follow pagination links),
                                           'none' (do not follow any links). Defaults to 'default'.
        """
        super().__init__(*args, **kwargs)

        if not start_url:
            raise ValueError("start_url must be provided")

        self.start_urls = [start_url]
        self.use_playwright = str(use_playwright).lower() in ["true", "1", "yes"]
        self.crawl_strategy = crawl_strategy

        if allowed_domains:
            self.allowed_domains = [d.strip() for d in allowed_domains.split(",")]
        else:
            parsed_uri = urlparse(start_url)
            self.allowed_domains = [parsed_uri.netloc] if parsed_uri.netloc else []
            if not self.allowed_domains:
                logger.warning(
                    f"Could not derive allowed_domain from start_url: {start_url}. Crawling might be restricted."
                )

        self.custom_settings = {
            "DEPTH_LIMIT": int(depth_limit),
        }

        logger.info(f"Initialized MediaSpider:")
        logger.info(f"  Start URL: {self.start_urls[0]}")
        logger.info(f"  Allowed Domains: {self.allowed_domains}")
        logger.info(f"  Depth Limit: {depth_limit}")
        logger.info(f"  Use Playwright: {self.use_playwright}")
        logger.info(f"  Crawl Strategy: {self.crawl_strategy}")

    def start_requests(self):
        """Generates the initial request(s)."""
        for url in self.start_urls:
            yield scrapy.Request(
                url, callback=self.parse, meta={"playwright": self.use_playwright}
            )

    def parse(self, response):
        """
        Parses the response, extracts media URLs, yields Items, and potentially follows links.
        """
        page_url = response.url
        logger.info(
            f"Parsing page: {page_url} (Depth: {response.meta.get('depth', 0)})"
        )
        if self.use_playwright and "playwright" in response.flags:
            logger.debug(f"Page rendered with Playwright: {page_url}")

        extracted_media = set()

        for src in response.css("img::attr(src)").getall():
            abs_url = response.urljoin(src.strip())
            if self._is_valid_media_url(abs_url, "image"):
                extracted_media.add((abs_url, "image"))

        for src in response.css("audio::attr(src)").getall():
            abs_url = response.urljoin(src.strip())
            if self._is_valid_media_url(abs_url, "audio"):
                extracted_media.add((abs_url, "audio"))

        for href in response.css("a::attr(href)").getall():
            abs_url = response.urljoin(href.strip())
            if self._is_valid_media_url(abs_url, "image"):
                extracted_media.add((abs_url, "image"))
            elif self._is_valid_media_url(abs_url, "audio"):
                extracted_media.add((abs_url, "audio"))

        for src in response.css("source::attr(src)").getall():
            abs_url = response.urljoin(src.strip())

            if self._is_valid_media_url(abs_url, "image"):
                extracted_media.add((abs_url, "image"))
            elif self._is_valid_media_url(abs_url, "audio"):
                extracted_media.add((abs_url, "audio"))

        found_count = 0
        for media_url, media_type in extracted_media:
            yield MediaItem(
                page_url=page_url, media_url=media_url, media_type=media_type
            )
            found_count += 1
        if found_count > 0:
            logger.info(f"Found {found_count} potential media items on {page_url}")

        if self.crawl_strategy == "none":
            logger.debug(
                f"Crawl strategy is 'none', not following links from {page_url}"
            )
            return

        if self.crawl_strategy == "pagination_only":
            logger.debug(
                f"Crawl strategy is 'pagination_only', looking for pagination links on {page_url}"
            )
            link_selectors = self.PAGINATION_SELECTORS
        else:
            logger.debug(
                f"Crawl strategy is 'default', looking for all valid links on {page_url}"
            )
            link_selectors = ["a::attr(href)"]

        followed_count = 0
        processed_links_on_page = set()

        for selector in link_selectors:
            for href in response.css(selector).getall():
                next_page_url = response.urljoin(href.strip())

                if self._is_valid_crawl_url(next_page_url, processed_links_on_page):
                    processed_links_on_page.add(next_page_url)
                    yield scrapy.Request(
                        next_page_url,
                        callback=self.parse,
                        meta={"playwright": self.use_playwright},
                    )
                    followed_count += 1

        if followed_count > 0:
            logger.info(f"Following {followed_count} links from {page_url}")

    def _is_valid_media_url(self, url: str, expected_type: str) -> bool:
        """Checks if a URL seems like a valid media URL of the expected type."""
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme in ["http", "https"]:
            return False
        if not parsed.netloc:
            return False

        path = parsed.path.lower()
        if expected_type == "image":
            return any(path.endswith(ext) for ext in self.IMAGE_EXTENSIONS)
        elif expected_type == "audio":
            return any(path.endswith(ext) for ext in self.AUDIO_EXTENSIONS)
        return False

    def _is_valid_crawl_url(self, url: str, already_processed: set) -> bool:
        """Checks if a URL is valid for crawling further."""
        if not url or url in already_processed:
            return False
        parsed = urlparse(url)
        if not parsed.scheme in ["http", "https"]:
            return False
        if not parsed.netloc:
            return False

        path = parsed.path.lower()
        if any(
            path.endswith(ext) for ext in self.IMAGE_EXTENSIONS + self.AUDIO_EXTENSIONS
        ):
            return False

        return True
