import logging
from typing import List, Dict, Any, Optional
import numpy as np
import torch


from .models import MambaVisionModel, CLAPModel


STATUS_SUCCESS = 1
STATUS_FAILED_DOWNLOAD = 2
STATUS_FAILED_PROCESSING = 3
STATUS_FAILED_UNSUPPORTED_TYPE = 4


MEDIA_TYPE_IMAGE = 1
MEDIA_TYPE_AUDIO = 2
MEDIA_TYPE_UNKNOWN = 0


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)


class Extractor:
    """
    Orchestrates feature extraction using appropriate models based on media type.
    Manages instances of the underlying ML models. Handles mapping page_url to results.
    """

    def __init__(
        self,
        mamba_config: Optional[Dict[str, Any]] = None,
        clap_config: Optional[Dict[str, Any]] = None,
        device: Optional[str] = None,
    ):
        """
        Initializes the Extractor and loads the required ML models.
        (Constructor remains the same as before)
        """
        logger.info("Initializing Extractor...")

        mamba_args = mamba_config or {}
        clap_args = clap_config or {}
        if device:
            mamba_args["device"] = device
            clap_args["device"] = device

        try:
            self.mamba_vision_model = MambaVisionModel(**mamba_args)
            logger.info("MambaVisionModel initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize MambaVisionModel: {e}", exc_info=True)
            self.mamba_vision_model = None

        try:
            self.clap_model = CLAPModel(**clap_args)
            logger.info("CLAPModel initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize CLAPModel: {e}", exc_info=True)
            self.clap_model = None

        if not self.mamba_vision_model and not self.clap_model:
            raise RuntimeError(
                "Failed to initialize BOTH MambaVision and CLAP models. Extractor cannot function."
            )
        elif not self.mamba_vision_model:
            logger.warning(
                "MambaVisionModel failed to initialize. Image processing will not be available."
            )
        elif not self.clap_model:
            logger.warning(
                "CLAPModel failed to initialize. Audio processing will not be available."
            )

        logger.info("Extractor initialization complete.")

    def process_batch(
        self, items: List[Dict[str, Any]], apply_denoising: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Processes a batch of URLs, extracting features based on their media type.

        Args:
            items (List[Dict[str, Any]]): A list of dictionaries, where each dict
                must have 'page_url' (str), 'media_url' (str), and 'type' (int,
                matching MEDIA_TYPE_* constants).
            apply_denoising (bool): Flag indicating whether to apply denoising.

        Returns:
            List[Dict[str, Any]]: A list of result dictionaries, one for each input item,
                containing 'url' (this will be the PAGE URL), 'status' (int),
                'feature_vector' (Optional[np.ndarray]), and 'error_message' (Optional[str]).
        """
        logger.info(
            f"Extractor received batch of {len(items)} items. Denoising: {apply_denoising}"
        )

        media_to_page_map: Dict[str, str] = {}

        page_url_details: Dict[str, Dict[str, Any]] = {}

        image_media_urls_to_process: List[str] = []
        audio_media_urls_to_process: List[str] = []

        final_results: Dict[str, Dict[str, Any]] = {}

        for item in items:
            page_url = item.get("page_url")
            media_url = item.get("media_url")
            media_type = item.get("type", MEDIA_TYPE_UNKNOWN)

            if not page_url or not media_url:
                logger.warning(
                    f"Skipping item due to missing page_url or media_url: {item}"
                )

                continue

            media_to_page_map[media_url] = page_url
            page_url_details[page_url] = item

            status = None
            error_msg = None

            if media_type == MEDIA_TYPE_IMAGE:
                if self.mamba_vision_model:
                    image_media_urls_to_process.append(media_url)
                else:
                    status = STATUS_FAILED_PROCESSING
                    error_msg = "Image processing unavailable (model init failed)."
            elif media_type == MEDIA_TYPE_AUDIO:
                if self.clap_model:
                    audio_media_urls_to_process.append(media_url)
                else:
                    status = STATUS_FAILED_PROCESSING
                    error_msg = "Audio processing unavailable (model init failed)."
            else:
                status = STATUS_FAILED_UNSUPPORTED_TYPE
                error_msg = f"Unsupported or unknown media type: {media_type}"

            if status is not None:
                final_results[page_url] = {
                    "url": page_url,
                    "status": status,
                    "feature_vector": None,
                    "error_message": error_msg,
                }

        image_results_by_media_url: Dict[str, Optional[np.ndarray]] = {}
        if image_media_urls_to_process and self.mamba_vision_model:
            logger.info(
                f"Processing {len(image_media_urls_to_process)} image media URLs..."
            )
            try:
                image_results_by_media_url = self.mamba_vision_model.get_features_batch(
                    image_media_urls_to_process
                )
                logger.info("Image batch processing complete.")
            except Exception as e:
                logger.error(
                    f"Error during MambaVision batch processing: {e}", exc_info=True
                )

                for media_url in image_media_urls_to_process:
                    page_url = media_to_page_map.get(media_url)
                    if page_url and page_url not in final_results:
                        final_results[page_url] = {
                            "url": page_url,
                            "status": STATUS_FAILED_PROCESSING,
                            "feature_vector": None,
                            "error_message": f"Image batch processing error: {e}",
                        }

        audio_results_by_media_url: Dict[str, Optional[np.ndarray]] = {}
        if audio_media_urls_to_process and self.clap_model:
            logger.info(
                f"Processing {len(audio_media_urls_to_process)} audio media URLs..."
            )
            try:
                audio_results_by_media_url = self.clap_model.get_features_batch(
                    audio_media_urls_to_process
                )
                logger.info("Audio batch processing complete.")
            except Exception as e:
                logger.error(f"Error during CLAP batch processing: {e}", exc_info=True)

                for media_url in audio_media_urls_to_process:
                    page_url = media_to_page_map.get(media_url)
                    if page_url and page_url not in final_results:
                        final_results[page_url] = {
                            "url": page_url,
                            "status": STATUS_FAILED_PROCESSING,
                            "feature_vector": None,
                            "error_message": f"Audio batch processing error: {e}",
                        }

        logger.info("Aggregating final results keyed by page_url...")
        output_list: List[Dict[str, Any]] = []

        for page_url, original_item_details in page_url_details.items():

            if page_url in final_results:
                output_list.append(final_results[page_url])
                continue

            media_url = original_item_details.get("media_url")
            media_type = original_item_details.get("type")
            feature_vector_data = None

            if media_type == MEDIA_TYPE_IMAGE:
                feature_vector_data = image_results_by_media_url.get(media_url)
            elif media_type == MEDIA_TYPE_AUDIO:
                feature_vector_data = audio_results_by_media_url.get(media_url)

            status = (
                STATUS_SUCCESS
                if feature_vector_data is not None
                else STATUS_FAILED_PROCESSING
            )
            error_msg = (
                None
                if status == STATUS_SUCCESS
                else "Processing failed (download or model internal error)."
            )

            result_entry = {
                "url": page_url,
                "status": status,
                "feature_vector": feature_vector_data,
                "error_message": error_msg,
            }
            final_results[page_url] = result_entry
            output_list.append(result_entry)

        logger.info(
            f"Extractor finished processing. Returning {len(output_list)} results."
        )
        return output_list

    def process_batch_bytes(
        self, items: List[Dict[str, Any]], apply_denoising: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Processes a batch of byte-based media items, extracting features based on their media type.

        Args:
            items (List[Dict[str, Any]]): A list of dictionaries, where each dict
                must have 'ref_id' (str), 'content' (bytes), and 'type' (int,
                matching MEDIA_TYPE_* constants).
            apply_denoising (bool): Flag indicating whether to apply denoising.

        Returns:
            List[Dict[str, Any]]: A list of result dictionaries, one for each input item,
                containing 'url' (this will be the REF_ID), 'status' (int),
                'feature_vector' (Optional[np.ndarray]), and 'error_message' (Optional[str]).
        """
        logger.info(
            f"Extractor received batch of {len(items)} byte items. Denoising: {apply_denoising}"
        )

        ref_id_details: Dict[str, Dict[str, Any]] = {}

        image_bytes_to_process: List[bytes] = []
        audio_bytes_to_process: List[bytes] = []
        image_ref_ids: List[str] = []
        audio_ref_ids: List[str] = []

        final_results: Dict[str, Dict[str, Any]] = {}

        for item in items:
            content = item.get("content")
            ref_id = item.get("ref_id")
            media_type = item.get("type", MEDIA_TYPE_UNKNOWN)

            if not content or not ref_id:
                logger.warning(
                    f"Skipping item due to missing ref_id or content: {item}"
                )
                continue

            ref_id_details[ref_id] = item

            status = None
            error_msg = None

            if media_type == MEDIA_TYPE_IMAGE:
                if self.mamba_vision_model:
                    image_bytes_to_process.append(content)
                    image_ref_ids.append(ref_id)
                else:
                    status = STATUS_FAILED_PROCESSING
                    error_msg = "Image processing unavailable (model init failed)."
            elif media_type == MEDIA_TYPE_AUDIO:
                if self.clap_model:
                    audio_bytes_to_process.append(content)
                    audio_ref_ids.append(ref_id)
                else:
                    status = STATUS_FAILED_PROCESSING
                    error_msg = "Audio processing unavailable (model init failed)."
            else:
                status = STATUS_FAILED_UNSUPPORTED_TYPE
                error_msg = f"Unsupported or unknown media type: {media_type}"

            if status is not None:
                final_results[ref_id] = {
                    "url": ref_id,
                    "status": status,
                    "feature_vector": None,
                    "error_message": error_msg,
                }

        image_results_by_ref_id: Dict[str, Optional[np.ndarray]] = {}
        if image_bytes_to_process and self.mamba_vision_model:
            logger.info(f"Processing {len(image_bytes_to_process)} images (bytes)...")
            try:

                raw_results = self.mamba_vision_model.get_features_batch_from_bytes(
                    image_bytes_to_process, apply_denoising
                )

                image_results_by_ref_id = {
                    ref_id: raw_results.get(f"uploaded_image_{i}")
                    for i, ref_id in enumerate(image_ref_ids)
                }
                logger.info("Image batch processing (bytes) complete.")
            except Exception as e:
                logger.error(
                    f"Error during MambaVision batch processing (bytes): {e}",
                    exc_info=True,
                )
                for ref_id in image_ref_ids:
                    if ref_id not in final_results:
                        final_results[ref_id] = {
                            "url": ref_id,
                            "status": STATUS_FAILED_PROCESSING,
                            "feature_vector": None,
                            "error_message": f"Image batch processing error: {e}",
                        }

        audio_results_by_ref_id: Dict[str, Optional[np.ndarray]] = {}
        if audio_bytes_to_process and self.clap_model:
            logger.info(
                f"Processing {len(audio_bytes_to_process)} audio files (bytes)..."
            )
            try:

                raw_results = self.clap_model.get_features_batch_from_bytes(
                    audio_bytes_to_process, apply_denoising
                )
                audio_results_by_ref_id = {
                    ref_id: raw_results.get(f"uploaded_audio_{i}")
                    for i, ref_id in enumerate(audio_ref_ids)
                }
                logger.info("Audio batch processing (bytes) complete.")
            except Exception as e:
                logger.error(
                    f"Error during CLAP batch processing (bytes): {e}", exc_info=True
                )
                for ref_id in audio_ref_ids:
                    if ref_id not in final_results:
                        final_results[ref_id] = {
                            "url": ref_id,
                            "status": STATUS_FAILED_PROCESSING,
                            "feature_vector": None,
                            "error_message": f"Audio batch processing error: {e}",
                        }

        logger.info("Aggregating final results keyed by ref_id...")
        output_list: List[Dict[str, Any]] = []

        for ref_id, original_item_details in ref_id_details.items():

            if ref_id in final_results:
                output_list.append(final_results[ref_id])
                continue

            media_type = original_item_details.get("type")
            feature_vector_data = None

            if media_type == MEDIA_TYPE_IMAGE:
                feature_vector_data = image_results_by_ref_id.get(ref_id)
            elif media_type == MEDIA_TYPE_AUDIO:
                feature_vector_data = audio_results_by_ref_id.get(ref_id)

            status = (
                STATUS_SUCCESS
                if feature_vector_data is not None
                else STATUS_FAILED_PROCESSING
            )
            error_msg = (
                None
                if status == STATUS_SUCCESS
                else "Processing failed (download or model internal error)."
            )

            result_entry = {
                "url": ref_id,
                "status": status,
                "feature_vector": feature_vector_data,
                "error_message": error_msg,
            }
            final_results[ref_id] = result_entry
            output_list.append(result_entry)

        logger.info(
            f"Extractor finished processing (bytes). Returning {len(output_list)} results."
        )
        return output_list


if __name__ == "__main__":
    print("--- Extractor Example Usage ---")

    try:
        extractor = Extractor(device="cuda" if torch.cuda.is_available() else "cpu")

        test_items = [
            {
                "page_url": "http://page1.com/article",
                "media_url": "https://images.pexels.com/photos/20787/pexels-photo.jpg?auto=compress&cs=tinysrgb&dpr=1&w=500",
                "type": MEDIA_TYPE_IMAGE,
            },
            {
                "page_url": "http://page2.com/sounds",
                "media_url": "https://github.com/karolpiczak/ESC-50/raw/master/audio/1-100032-A-0.wav",
                "type": MEDIA_TYPE_AUDIO,
            },
            {
                "page_url": "http://page3.com/images",
                "media_url": "http://inv.alid.url/image.jpg",
                "type": MEDIA_TYPE_IMAGE,
            },
            {
                "page_url": "http://page4.com/home",
                "media_url": "https://www.google.com",
                "type": MEDIA_TYPE_IMAGE,
            },
            {
                "page_url": "http://page5.com/files",
                "media_url": "https://some.domain/file.txt",
                "type": MEDIA_TYPE_UNKNOWN,
            },
            {
                "page_url": "http://page6.com/music",
                "media_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "type": MEDIA_TYPE_AUDIO,
            },
        ]

        results = extractor.process_batch(test_items, apply_denoising=False)

        print("\n--- Final Aggregated Results ---")
        for res in results:
            status = res["status"]
            vec_shape = (
                res["feature_vector"].shape
                if res["feature_vector"] is not None
                else None
            )
            print(f"URL: {res['url']}")
            print(f"  Status: {status}")
            print(f"  Vector Shape: {vec_shape}")
            if res["error_message"]:
                print(f"  Error: {res['error_message']}")
            print("-" * 10)

    except RuntimeError as e:
        print(f"Could not run extractor example: {e}")
    except ImportError:

        import sys

        if "torch" not in sys.modules:
            print("Could not run example: PyTorch not installed.")
        else:
            print(
                "Could not run example due to other import error (check model init logs)."
            )
    except Exception as e:
        print(f"An unexpected error occurred during example: {e}")
