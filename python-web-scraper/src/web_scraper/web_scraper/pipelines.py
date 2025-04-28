import grpc
import logging
from itemadapter import ItemAdapter

try:

    from . import indexing_pb2
    from . import indexing_pb2_grpc

    GRPC_AVAILABLE = True
except ImportError as e:
    GRPC_AVAILABLE = False
    logging.error(
        f"ImportError loading gRPC modules (indexing_pb2*.py) from generated. "
        f"Ensure they were generated correctly. Error: {e}. Pipeline cannot communicate."
    )

from .items import MediaItem

logger = logging.getLogger(__name__)


MEDIA_TYPE_MAP_TO_PROTO = {
    "image": indexing_pb2.MediaType.IMAGE,
    "audio": indexing_pb2.MediaType.AUDIO,
}


class GoApiPipeline:

    def __init__(self, go_api_grpc_address, batch_size, job_id):
        if not GRPC_AVAILABLE:
            raise NotConfigured("gRPC modules not available or import failed.")
        self.go_api_grpc_address = go_api_grpc_address
        self.batch_size = batch_size

        self.job_id = job_id or "unknown-job"
        self.item_buffer = []
        self.channel = None
        self.stub = None

    @classmethod
    def from_crawler(cls, crawler):

        address = crawler.settings.get("GO_API_GRPC_ADDRESS")
        batch_size = crawler.settings.getint("PIPELINE_BATCH_SIZE", 100)

        job_id = crawler.settings.get("JOB_ID", None)
        if not address:
            raise NotConfigured("GO_API_GRPC_ADDRESS setting is missing.")
        return cls(go_api_grpc_address=address, batch_size=batch_size, job_id=job_id)

    def open_spider(self, spider):
        if not GRPC_AVAILABLE:
            return
        try:

            self.channel = grpc.insecure_channel(self.go_api_grpc_address)

            self.stub = indexing_pb2_grpc.IndexingServiceStub(self.channel)
            logger.info(
                f"[Job {self.job_id}] Connected to Go API gRPC at {self.go_api_grpc_address}"
            )
        except Exception as e:
            logger.error(
                f"[Job {self.job_id}] Failed to connect to Go API gRPC at {self.go_api_grpc_address}: {e}",
                exc_info=True,
            )
            self.channel = None
            self.stub = None

    def close_spider(self, spider):
        if self.stub and self.item_buffer:
            logger.info(
                f"[Job {self.job_id}] Spider closing, sending final batch of {len(self.item_buffer)} items to Go API."
            )
            self._send_batch()
        if self.channel:
            self.channel.close()
            logger.info(f"[Job {self.job_id}] Closed connection to Go API gRPC.")

    def process_item(self, item, spider):
        if not GRPC_AVAILABLE or not self.stub:
            logger.warning(
                f"[Job {self.job_id}] Dropping item due to unavailable gRPC connection/modules: {item.get('media_url')}"
            )
            return item

        if not isinstance(item, MediaItem):
            return item

        adapter = ItemAdapter(item)
        page_url = adapter.get("page_url")
        media_url = adapter.get("media_url")
        media_type_str = adapter.get("media_type")

        if not all([page_url, media_url, media_type_str]):
            logger.warning(
                f"[Job {self.job_id}] Skipping item with missing data: {item}"
            )
            return item

        proto_media_type = MEDIA_TYPE_MAP_TO_PROTO.get(
            media_type_str, indexing_pb2.MediaType.UNKNOWN
        )

        if proto_media_type == indexing_pb2.MediaType.UNKNOWN:
            logger.warning(
                f"[Job {self.job_id}] Skipping item with unknown media type '{media_type_str}': {media_url}"
            )
            return item

        scraped_item_proto = indexing_pb2.ScrapedItem(
            page_url=page_url, media_url=media_url, media_type=proto_media_type
        )
        self.item_buffer.append(scraped_item_proto)
        logger.debug(
            f"[Job {self.job_id}] Buffered item: page={page_url}, media={media_url}"
        )

        if len(self.item_buffer) >= self.batch_size:
            logger.info(
                f"[Job {self.job_id}] Buffer full ({len(self.item_buffer)} items), sending batch to Go API."
            )
            self._send_batch()

        return item

    def _send_batch(self):
        if not self.item_buffer or not self.stub:
            return

        request = indexing_pb2.ProcessScrapedItemsRequest(
            items=self.item_buffer, job_id=self.job_id
        )

        try:

            response = self.stub.ProcessScrapedItems(request, timeout=90)
            logger.info(
                f"[Job {self.job_id}] Sent batch of {len(self.item_buffer)} items to Go API. Response: {response.message}"
            )

            if response.items_failed > 0:
                logger.warning(
                    f"[Job {self.job_id}] Go API reported {response.items_failed} failures during batch processing."
                )

        except grpc.RpcError as e:
            logger.error(
                f"[Job {self.job_id}] gRPC error sending batch to Go API: {e.status()} - {e.details()}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"[Job {self.job_id}] Unexpected error sending batch to Go API: {e}",
                exc_info=True,
            )
        finally:
            self.item_buffer.clear()


class NotConfigured(Exception):
    pass
