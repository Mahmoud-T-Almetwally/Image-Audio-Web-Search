import grpc
import logging
from itemadapter import ItemAdapter


try:
    from src.generated import feature_pb2 
    from src.generated import feature_pb2_grpc 

    GRPC_AVAILABLE = True
except ImportError as e:
    GRPC_AVAILABLE = False
    import sys
    import os
    current_dir = os.path.dirname(__file__)
    src_dir_guess = os.path.abspath(os.path.join(current_dir, '..', '..'))
    logging.error(
        f"ImportError loading gRPC modules: {e}. Check paths relative to {current_dir}. "
        f"Expected 'generated' dir in '{src_dir_guess}'. sys.path: {sys.path}. "
        f"Pipeline cannot communicate."
    )

from .items import MediaItem

logger = logging.getLogger(__name__)


class FeatureExtractorPipeline:

    def __init__(self, feature_extractor_address, batch_size):
        if not GRPC_AVAILABLE:
            raise NotConfigured("gRPC modules not available.")
        self.feature_extractor_address = feature_extractor_address
        self.batch_size = batch_size
        self.item_buffer = []
        self.channel = None
        self.stub = None

    @classmethod
    def from_crawler(cls, crawler):
        address = crawler.settings.get("FEATURE_EXTRACTOR_ADDRESS")
        batch_size = crawler.settings.getint("PIPELINE_BATCH_SIZE", 100)
        if not address:
            raise NotConfigured("FEATURE_EXTRACTOR_ADDRESS setting is missing.")
        return cls(feature_extractor_address=address, batch_size=batch_size)

    def open_spider(self, spider):
        try:

            self.channel = grpc.insecure_channel(self.feature_extractor_address)

            self.stub = feature_pb2_grpc.FeatureServiceStub(self.channel)
            logger.info(
                f"Connected to Feature Extractor at {self.feature_extractor_address}"
            )
        except Exception as e:
            logger.error(
                f"Failed to connect to Feature Extractor at {self.feature_extractor_address}: {e}",
                exc_info=True,
            )

            self.channel = None
            self.stub = None

    def close_spider(self, spider):
        if self.stub and self.item_buffer:
            logger.info(
                f"Spider closing, sending final batch of {len(self.item_buffer)} items."
            )
            self._send_batch()
        if self.channel:
            self.channel.close()
            logger.info("Closed connection to Feature Extractor.")

    def process_item(self, item, spider):

        if not isinstance(item, MediaItem):
            return item

        if not self.stub:
            logger.warning(
                f"Dropping item due to unavailable connection to Feature Extractor: {item.get('media_url')}"
            )
            return item

        adapter = ItemAdapter(item)
        page_url = adapter.get("page_url")
        media_url = adapter.get("media_url")
        media_type_str = adapter.get("media_type")

        if not all([page_url, media_url, media_type_str]):
            logger.warning(f"Skipping item with missing data: {item}")
            return item

        proto_media_type = feature_pb2.MediaType.UNKNOWN
        if media_type_str == "image":
            proto_media_type = feature_pb2.MediaType.IMAGE
        elif media_type_str == "audio":
            proto_media_type = feature_pb2.MediaType.AUDIO

        if proto_media_type == feature_pb2.MediaType.UNKNOWN:
            logger.warning(
                f"Skipping item with unknown media type '{media_type_str}': {media_url}"
            )
            return item

        url_item_proto = feature_pb2.UrlItem(
            media_url=media_url, type=proto_media_type, page_url=page_url
        )
        self.item_buffer.append(url_item_proto)
        logger.debug(f"Buffered item: page={page_url}, media={media_url}")

        if len(self.item_buffer) >= self.batch_size:
            logger.info(f"Buffer full ({len(self.item_buffer)} items), sending batch.")
            self._send_batch()

        return item

    def _send_batch(self):
        if not self.item_buffer or not self.stub:
            return

        request = feature_pb2.ProcessUrlsRequest(
            items=self.item_buffer, apply_denoising=False
        )

        try:

            response = self.stub.ProcessUrls(request, timeout=60)
            logger.info(
                f"Sent batch of {len(self.item_buffer)} items. Received response (results count: {len(response.results)})."
            )

            for result in response.results:
                if result.status != feature_pb2.Status.SUCCESS:
                    logger.warning(
                        f"Feature extraction failed for {result.url} (originally media_url: {self._find_media_url(result.url)}): Status={result.status}, Msg={result.error_message}"
                    )

        except grpc.RpcError as e:
            logger.error(
                f"gRPC error sending batch to Feature Extractor: {e.status()} - {e.details()}",
                exc_info=True,
            )

        except Exception as e:
            logger.error(f"Unexpected error sending batch: {e}", exc_info=True)
        finally:

            self.item_buffer.clear()

    def _find_media_url(self, page_url_in_result):

        return page_url_in_result


class NotConfigured(Exception):
    pass
