import grpc
from concurrent import futures
import time
import logging
import os
import sys


script_dir = os.path.dirname(os.path.abspath(__file__))

src_dir = os.path.dirname(script_dir)


if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


from extraction.extractor import Extractor
from .feature_service import FeatureExtractionService


from generated import feature_pb2_grpc


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger(__name__)


_SERVER_ADDRESS_ENV = "FEATURE_SERVER_ADDRESS"
_DEFAULT_SERVER_ADDRESS = "[::]:50051"
_MAX_WORKERS_ENV = "FEATURE_MAX_WORKERS"
_DEFAULT_MAX_WORKERS = 10

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def serve():
    """Starts the gRPC server."""

    server_address = os.environ.get(_SERVER_ADDRESS_ENV, _DEFAULT_SERVER_ADDRESS)
    max_workers = int(os.environ.get(_MAX_WORKERS_ENV, _DEFAULT_MAX_WORKERS))

    logger.info("--- Initializing Feature Extraction Service ---")

    try:
        extractor = Extractor(device=None)
    except RuntimeError as e:
        logger.critical(
            f"Failed to initialize Extractor: {e}. Server cannot start.", exc_info=True
        )
        return
    except Exception as e:
        logger.critical(
            f"An unexpected error occurred during Extractor initialization: {e}. Server cannot start.",
            exc_info=True,
        )
        return

    feature_service = FeatureExtractionService(
        extractor=extractor,
        filter_images=True,
        max_image_size_mb=25,
        filter_audio=True,
        max_audio_size_mb=150,
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    feature_pb2_grpc.add_FeatureServiceServicer_to_server(feature_service, server)

    try:
        server.add_insecure_port(server_address)
        server.start()
        logger.info(f"🚀 Feature Extraction Server started successfully!")
        logger.info(f"Listening on: {server_address}")
        logger.info(f"Max workers: {max_workers}")

        server.wait_for_termination()

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

        server.stop(10)
        logger.info("Server shut down.")


if __name__ == "__main__":
    serve()
