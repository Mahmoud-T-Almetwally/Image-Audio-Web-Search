import logging
import numpy as np
from typing import List, Dict, Any, Tuple

from generated import feature_pb2, feature_pb2_grpc

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

    def __init__(
        self,
        extractor: Extractor,
        filter_images: bool = True,
        max_image_size_mb: int = 20,
        filter_audio: bool = True,
        max_audio_size_mb: int = 100,
    ):
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
        logger.info(
            f"Received ProcessUrls request with {len(request.items)} items. Denoising: {request.apply_denoising}"
        )

        response = feature_pb2.ProcessUrlsResponse()

        items_for_filtering: Dict[str, Dict[str, Any]] = {}

        original_items_map_by_page: Dict[str, feature_pb2.UrlItem] = {}

        early_failures_by_page: Dict[str, Tuple[feature_pb2.Status, str]] = {}

        for item in request.items:
            page_url = item.page_url
            media_url = item.media_url

            if not page_url or not media_url:
                logger.warning(
                    f"Received item with missing page_url ('{page_url}') or media_url ('{media_url}')."
                )

                continue

            original_items_map_by_page[page_url] = item

            item_type_internal = TYPE_MAP_FROM_PROTO.get(item.type)

            if (
                item_type_internal == MEDIA_TYPE_IMAGE
                or item_type_internal == MEDIA_TYPE_AUDIO
            ):
                items_for_filtering[media_url] = {
                    "page_url": page_url,
                    "type": item_type_internal,
                }
            else:
                logger.warning(
                    f"Received item with unknown/unsupported type ({item.type}) for page: {page_url}, media: {media_url}"
                )
                early_failures_by_page[page_url] = (
                    feature_pb2.Status.FAILED_UNSUPPORTED_TYPE,
                    f"Unsupported media type: {item.type}",
                )

        image_media_urls = [
            m_url
            for m_url, data in items_for_filtering.items()
            if data["type"] == MEDIA_TYPE_IMAGE
        ]
        audio_media_urls = [
            m_url
            for m_url, data in items_for_filtering.items()
            if data["type"] == MEDIA_TYPE_AUDIO
        ]

        valid_image_media_urls = image_media_urls
        if self.filter_images and image_media_urls:
            logger.info(f"Filtering {len(image_media_urls)} image media URLs...")
            valid_image_media_urls = filter_urls_by_headers(
                image_media_urls, "image", max_size_bytes=self.max_image_size_bytes
            )
            for media_url in image_media_urls:
                if media_url not in valid_image_media_urls:
                    page_url = items_for_filtering[media_url]["page_url"]
                    early_failures_by_page[page_url] = (
                        feature_pb2.Status.FAILED_DOWNLOAD,
                        "Failed image pre-filtering (HEAD check on media_url)",
                    )

        valid_audio_media_urls = audio_media_urls
        if self.filter_audio and audio_media_urls:
            logger.info(f"Filtering {len(audio_media_urls)} audio media URLs...")
            valid_audio_media_urls = filter_urls_by_headers(
                audio_media_urls, "audio", max_size_bytes=self.max_audio_size_bytes
            )
            for media_url in audio_media_urls:
                if media_url not in valid_audio_media_urls:
                    page_url = items_for_filtering[media_url]["page_url"]
                    early_failures_by_page[page_url] = (
                        feature_pb2.Status.FAILED_DOWNLOAD,
                        "Failed audio pre-filtering (HEAD check on media_url)",
                    )

        items_to_process_extractor: List[Dict[str, Any]] = []
        for media_url in valid_image_media_urls:
            details = items_for_filtering[media_url]
            items_to_process_extractor.append(
                {
                    "page_url": details["page_url"],
                    "media_url": media_url,
                    "type": MEDIA_TYPE_IMAGE,
                }
            )
        for media_url in valid_audio_media_urls:
            details = items_for_filtering[media_url]
            items_to_process_extractor.append(
                {
                    "page_url": details["page_url"],
                    "media_url": media_url,
                    "type": MEDIA_TYPE_AUDIO,
                }
            )

        extractor_results_by_page: Dict[str, Dict[str, Any]] = {}
        if items_to_process_extractor:
            try:
                raw_extractor_results = self.extractor.process_batch(
                    items_to_process_extractor, apply_denoising=request.apply_denoising
                )

                for res in raw_extractor_results:
                    extractor_results_by_page[res["url"]] = res

            except Exception as e:
                logger.error(
                    f"Critical error during extractor.process_batch: {e}", exc_info=True
                )

                for item in items_to_process_extractor:
                    page_url = item["page_url"]
                    if page_url not in early_failures_by_page:
                        early_failures_by_page[page_url] = (
                            feature_pb2.Status.FAILED_PROCESSING,
                            f"Extractor batch processing error: {e}",
                        )

        logger.info("Constructing gRPC response...")
        for page_url, original_item in original_items_map_by_page.items():

            feature_result = feature_pb2.FeatureResult(url=page_url)

            if page_url in early_failures_by_page:

                status_enum, error_msg = early_failures_by_page[page_url]
                feature_result.status = status_enum
                feature_result.error_message = error_msg
            elif page_url in extractor_results_by_page:

                internal_result = extractor_results_by_page[page_url]
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
                            f"Failed to serialize feature vector for page {page_url} (media: {original_item.media_url}): {e}"
                        )
                        feature_result.status = feature_pb2.Status.FAILED_PROCESSING
                        feature_result.error_message = (
                            f"Failed to serialize vector: {e}"
                        )
                        feature_result.feature_vector = b""
            else:

                logger.error(
                    f"Page URL {page_url} (media: {original_item.media_url}) was not found in early failures or extractor results."
                )
                feature_result.status = feature_pb2.Status.FAILED_PROCESSING
                feature_result.error_message = (
                    "Internal Server Error: Result not found after processing."
                )

            response.results.append(feature_result)

        logger.info(
            f"Sending ProcessUrls response with {len(response.results)} results."
        )
        return response
