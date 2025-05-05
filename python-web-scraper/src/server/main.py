import grpc
from concurrent import futures
import asyncio
import logging
import os
import sys


script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(script_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


from server.scrape_service import ScraperService


try:
    from generated import scrape_pb2_grpc
except ImportError:
    logging.critical(
        "Failed to import generated gRPC modules (scrape_pb2_grpc). Please ensure they are generated correctly in 'src/generated'."
    )
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger(__name__)


_SERVER_ADDRESS_ENV = "SCRAPE_SERVER_ADDRESS"
_DEFAULT_SERVER_ADDRESS = "[::]:50052"
_MAX_WORKERS_ENV = "SCRAPE_MAX_WORKERS"
_DEFAULT_MAX_WORKERS = 10

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


async def serve():
    """Starts the gRPC server for the Scraper Service."""

    server_address = os.environ.get(_SERVER_ADDRESS_ENV, _DEFAULT_SERVER_ADDRESS)
    max_workers = int(os.environ.get(_MAX_WORKERS_ENV, _DEFAULT_MAX_WORKERS))

    print(server_address, max_workers)

    logger.info("--- Initializing Scraper Service ---")

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=max_workers))

    scraper_service = ScraperService()

    scrape_pb2_grpc.add_ScraperServiceServicer_to_server(scraper_service, server)

    try:
        server.add_insecure_port(server_address)
        await server.start()
        logger.info(f"🚀 Scraper Service Server started successfully!")
        logger.info(f"Listening on: {server_address}")
        logger.info(f"Max workers: {max_workers}")

        await server.wait_for_termination()

    except OSError as e:
        logger.critical(
            f"Failed to bind to address {server_address}. Port might be in use or permission denied: {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.critical(
            f"An unexpected error occurred while starting or running the server: {e}",
            exc_info=True,
        )
    finally:
        logger.info("Attempting to stop the server...")

        await server.stop(10)
        logger.info("Server shut down.")


if __name__ == "__main__":

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via KeyboardInterrupt.")
