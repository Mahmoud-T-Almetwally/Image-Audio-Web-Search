import logging
import uuid


from src.generated import scrape_pb2
from src.generated import scrape_pb2_grpc


from src.utils.utils import (
    validate_url,
    validate_depth,
    validate_crawl_strategy,
    extract_domain,
)


from .trigger import launch_scrapy_crawl_async

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)


ALLOWED_CRAWL_STRATEGIES = ["default", "pagination_only", "none"]
DEFAULT_CRAWL_STRATEGY = "default"
DEFAULT_DEPTH_LIMIT = 2
DEFAULT_USE_PLAYWRIGHT = True


class ScraperService(scrape_pb2_grpc.ScraperServiceServicer):
    """
    Implementation of the ScraperService gRPC service.
    Handles requests to start scrape jobs.
    """

    def __init__(self):

        logger.info("ScraperService initialized.")

    async def StartScrape(
        self, request: scrape_pb2.StartScrapeRequest, context
    ) -> scrape_pb2.StartScrapeResponse:
        """
        Handles the gRPC request to start a scrape job.
        Validates parameters and uses the trigger module to launch the crawl.
        """
        logger.info(f"Received StartScrape request for URL: {request.start_url}")

        start_url = request.start_url
        if not validate_url(start_url):
            logger.warning(
                f"Rejected StartScrape request: Invalid start_url: {start_url}"
            )
            return scrape_pb2.StartScrapeResponse(
                job_id="",
                status=scrape_pb2.Status.REJECTED,
                message=f"Invalid start_url provided: {start_url}",
            )

        allowed_domains_str = request.allowed_domains
        allowed_domains_list = []
        if allowed_domains_str:
            allowed_domains_list = [d.strip() for d in allowed_domains_str.split(",")]

        final_allowed_domains = allowed_domains_list or [extract_domain(start_url)]
        if not final_allowed_domains or not final_allowed_domains[0]:
            logger.warning(
                f"Rejected StartScrape request: Could not determine allowed_domains for {start_url}"
            )
            return scrape_pb2.StartScrapeResponse(
                job_id="",
                status=scrape_pb2.Status.REJECTED,
                message=f"Could not determine allowed_domains for start_url: {start_url}",
            )

        depth_limit = request.depth_limit
        if not validate_depth(depth_limit) or depth_limit <= 0:
            logger.info(
                f"Using default depth_limit={DEFAULT_DEPTH_LIMIT} for request (received {depth_limit})"
            )
            depth_limit = DEFAULT_DEPTH_LIMIT

        crawl_strategy = request.crawl_strategy.lower().strip()
        if not validate_crawl_strategy(crawl_strategy, ALLOWED_CRAWL_STRATEGIES):
            logger.info(
                f"Using default crawl_strategy='{DEFAULT_CRAWL_STRATEGY}' for request (received '{crawl_strategy}')"
            )
            crawl_strategy = DEFAULT_CRAWL_STRATEGY

        use_playwright = (
            request.use_playwright
            if request.HasField("use_playwright")
            else DEFAULT_USE_PLAYWRIGHT
        )

        job_id = str(uuid.uuid4())
        logger.info(f"Generated Job ID: {job_id} for URL: {start_url}")

        try:

            await launch_scrapy_crawl_async(
                job_id=job_id,
                start_url=start_url,
                allowed_domains=",".join(final_allowed_domains),
                depth_limit=depth_limit,
                use_playwright=use_playwright,
                crawl_strategy=crawl_strategy,
            )

            logger.info(f"Successfully triggered Scrapy crawl for Job ID: {job_id}")

            return scrape_pb2.StartScrapeResponse(
                job_id=job_id,
                status=scrape_pb2.Status.ACCEPTED,
                message="Scrape job accepted and initiated.",
            )

        except Exception as e:
            logger.error(
                f"Failed to trigger Scrapy crawl for Job ID: {job_id}: {e}",
                exc_info=True,
            )
            return scrape_pb2.StartScrapeResponse(
                job_id=job_id,
                status=scrape_pb2.Status.REJECTED,
                message=f"Internal server error during crawl initiation: {e}",
            )
