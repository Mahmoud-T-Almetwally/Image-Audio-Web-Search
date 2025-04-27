import logging
import numpy as np
from typing import List, Dict, Any


from generated import feature_pb2
from generated import feature_pb2_grpc


from extraction.extractor import (
    Extractor,
    STATUS_SUCCESS,
    STATUS_FAILED_DOWNLOAD,
    STATUS_FAILED_PROCESSING,
    STATUS_FAILED_UNSUPPORTED_TYPE,
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_AUDIO,
)
from utils.network import filter_urls_by_headers

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)


TYPE_MAP_TO_PROTO = {
    MEDIA_TYPE_IMAGE: feature_pb2.MediaType.IMAGE,
    MEDIA_TYPE_AUDIO: feature_pb2.MediaType.AUDIO,
}

TYPE_MAP_FROM_PROTO = {v: k for k, v in TYPE_MAP_TO_PROTO.items()}


STATUS_MAP_TO_PROTO = {
    STATUS_SUCCESS: feature_pb2.Status.SUCCESS,
    STATUS_FAILED_DOWNLOAD: feature_pb2.Status.FAILED_DOWNLOAD,
    STATUS_FAILED_PROCESSING: feature_pb2.Status.FAILED_PROCESSING,
    STATUS_FAILED_UNSUPPORTED_TYPE: feature_pb2.Status.FAILED_UNSUPPORTED_TYPE,
}


class FeatureExtractionService(feature_pb2_grpc.FeatureServiceServicer):
    """
    Implementation of the FeatureService gRPC service.
    Uses an Extractor instance to handle feature extraction logic.
    """

    def __init__(
        self,
        extractor: Extractor,
        filter_images: bool = True,
        max_image_size_mb: int = 20,
        filter_audio: bool = True,
        max_audio_size_mb: int = 100,
    ):
        """
        Initializes the service.

        Args:
            extractor: An initialized instance of the Extractor class.
            filter_images: Whether to pre-filter image URLs using HEAD requests.
            max_image_size_mb: Max image size in MB for filtering.
            filter_audio: Whether to pre-filter audio URLs using HEAD requests.
            max_audio_size_mb: Max audio size in MB for filtering.
        """
        if extractor is None:
            raise ValueError("Extractor instance cannot be None")
        self.extractor = extractor
        self.filter_images = filter_images
        self.max_image_size_bytes = (
            max_image_size_mb * 1024 * 1024 if max_image_size_mb else None
        )
        self.filter_audio = filter_audio
        self.max_audio_size_bytes = (
            max_audio_size_mb * 1024 * 1024 if max_audio_size_mb else None
        )
        logger.info(
            f"FeatureExtractionService initialized. Image filtering: {self.filter_images}, Audio filtering: {self.filter_audio}"
        )

    def ProcessUrls(
        self, request: feature_pb2.ProcessUrlsRequest, context
    ) -> feature_pb2.ProcessUrlsResponse:
        """
        Handles the gRPC request to process a batch of URLs.
        """
        logger.info(
            f"Received ProcessUrls request with {len(request.items)} items. Denoising: {request.apply_denoising}"
        )

        response = feature_pb2.ProcessUrlsResponse()
        items_to_process: List[Dict[str, Any]] = []
        urls_failed_filtering: Dict[str, str] = {}

        image_urls_from_request: List[str] = []
        audio_urls_from_request: List[str] = []
        unknown_type_items: List[feature_pb2.UrlItem] = []
        original_items_map: Dict[str, feature_pb2.UrlItem] = {}

        for item in request.items:
            original_items_map[item.url] = item
            item_type_internal = TYPE_MAP_FROM_PROTO.get(item.type)
            if item_type_internal == MEDIA_TYPE_IMAGE:
                image_urls_from_request.append(item.url)
            elif item_type_internal == MEDIA_TYPE_AUDIO:
                audio_urls_from_request.append(item.url)
            else:
                unknown_type_items.append(item)
                logger.warning(
                    f"Received item with unknown/unsupported type ({item.type}) for URL: {item.url}"
                )
                urls_failed_filtering[item.url] = f"Unsupported media type: {item.type}"

        valid_image_urls = image_urls_from_request
        if self.filter_images and image_urls_from_request:
            logger.info(f"Filtering {len(image_urls_from_request)} image URLs...")
            valid_image_urls = filter_urls_by_headers(
                image_urls_from_request,
                "image",
                max_size_bytes=self.max_image_size_bytes,
            )
            for url in image_urls_from_request:
                if url not in valid_image_urls:
                    urls_failed_filtering[url] = (
                        "Failed image pre-filtering (HEAD check)"
                    )

        valid_audio_urls = audio_urls_from_request
        if self.filter_audio and audio_urls_from_request:
            logger.info(f"Filtering {len(audio_urls_from_request)} audio URLs...")
            valid_audio_urls = filter_urls_by_headers(
                audio_urls_from_request,
                "audio",
                max_size_bytes=self.max_audio_size_bytes,
            )
            for url in audio_urls_from_request:
                if url not in valid_audio_urls:
                    urls_failed_filtering[url] = (
                        "Failed audio pre-filtering (HEAD check)"
                    )

        for url in valid_image_urls:
            items_to_process.append({"url": url, "type": MEDIA_TYPE_IMAGE})
        for url in valid_audio_urls:
            items_to_process.append({"url": url, "type": MEDIA_TYPE_AUDIO})

        extractor_results: List[Dict[str, Any]] = []
        if items_to_process:
            try:
                extractor_results = self.extractor.process_batch(
                    items_to_process, apply_denoising=request.apply_denoising
                )
            except Exception as e:
                logger.error(
                    f"Critical error during extractor.process_batch: {e}", exc_info=True
                )

                for item in items_to_process:
                    urls_failed_filtering[item["url"]] = (
                        f"Extractor batch processing error: {e}"
                    )

        results_map: Dict[str, Dict[str, Any]] = {
            res["url"]: res for res in extractor_results
        }

        logger.info("Constructing gRPC response...")
        for url, original_item in original_items_map.items():
            feature_result = feature_pb2.FeatureResult(url=url)

            if url in urls_failed_filtering:

                feature_result.status = feature_pb2.Status.FAILED_DOWNLOAD
                feature_result.error_message = urls_failed_filtering[url]
            elif url in results_map:

                internal_result = results_map[url]
                internal_status = internal_result["status"]

                feature_result.status = STATUS_MAP_TO_PROTO.get(
                    internal_status, feature_pb2.Status.STATUS_UNKNOWN
                )
                feature_result.error_message = (
                    internal_result.get("error_message", "") or ""
                )

                if (
                    internal_status == STATUS_SUCCESS
                    and internal_result.get("feature_vector") is not None
                ):
                    feature_vector_np: np.ndarray = internal_result["feature_vector"]
                    try:

                        feature_result.feature_vector = feature_vector_np.astype(
                            np.float32
                        ).tobytes()
                    except Exception as e:
                        logger.error(
                            f"Failed to serialize feature vector for {url}: {e}"
                        )
                        feature_result.status = feature_pb2.Status.FAILED_PROCESSING
                        feature_result.error_message = (
                            f"Failed to serialize vector: {e}"
                        )
                        feature_result.feature_vector = b""
            else:

                logger.error(
                    f"URL {url} was not found in filtering failures or extractor results."
                )
                feature_result.status = feature_pb2.Status.FAILED_PROCESSING
                feature_result.error_message = (
                    "Internal Server Error: Result not found."
                )

            response.results.append(feature_result)

        logger.info(
            f"Sending ProcessUrls response with {len(response.results)} results."
        )
        return response
