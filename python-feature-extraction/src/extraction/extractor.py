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
    Manages instances of the underlying ML models.
    """

    def __init__(
        self,
        mamba_config: Optional[Dict[str, Any]] = None,
        clap_config: Optional[Dict[str, Any]] = None,
        device: Optional[str] = None,
    ):
        """
        Initializes the Extractor and loads the required ML models.

        Args:
            mamba_config (Optional[Dict[str, Any]]): Configuration arguments
                passed directly to MambaVisionModel constructor
                (e.g., {'model_name': '...', 'input_res': (3, 224, 224)}).
            clap_config (Optional[Dict[str, Any]]): Configuration arguments
                passed directly to CLAPModel constructor
                (e.g., {'model_name': '...', 'processor_name': '...'}).
            device (Optional[str]): Target device ('cuda', 'cpu'). Overrides
                device settings within mamba_config/clap_config if provided here.
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
        self, items: List[Dict[str, Any]], apply_denoising: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Processes a batch of URLs, extracting features based on their media type.

        Args:
            items (List[Dict[str, Any]]): A list of dictionaries, where each dict
                should have at least 'url' (str) and 'type' (int, matching MEDIA_TYPE_* constants).
            apply_denoising (bool): Flag indicating whether to apply denoising
                                    during processing (passed down to model classes).

        Returns:
            List[Dict[str, Any]]: A list of result dictionaries, one for each input item,
                containing 'url', 'status' (int, matching STATUS_* constants),
                'feature_vector' (Optional[np.ndarray]), and 'error_message' (Optional[str]).
        """
        logger.info(
            f"Extractor received batch of {len(items)} items. Denoising: {apply_denoising}"
        )

        image_urls_to_process: List[str] = []
        audio_urls_to_process: List[str] = []
        url_map: Dict[str, int] = {
            item["url"]: item.get("type", MEDIA_TYPE_UNKNOWN) for item in items
        }

        final_results: Dict[str, Dict[str, Any]] = {}

        for item in items:
            url = item["url"]
            media_type = url_map[url]

            status = STATUS_FAILED_UNSUPPORTED_TYPE
            error_msg = f"Unsupported or unknown media type: {media_type}"

            if media_type == MEDIA_TYPE_IMAGE:
                if self.mamba_vision_model:
                    image_urls_to_process.append(url)
                    status = None
                    error_msg = None
                else:
                    status = STATUS_FAILED_PROCESSING
                    error_msg = "Image processing unavailable (model init failed)."

            elif media_type == MEDIA_TYPE_AUDIO:
                if self.clap_model:
                    audio_urls_to_process.append(url)
                    status = None
                    error_msg = None
                else:
                    status = STATUS_FAILED_PROCESSING
                    error_msg = "Audio processing unavailable (model init failed)."

            if status is not None:
                final_results[url] = {
                    "url": url,
                    "status": status,
                    "feature_vector": None,
                    "error_message": error_msg,
                }

        image_results: Dict[str, Optional[np.ndarray]] = {}
        if image_urls_to_process and self.mamba_vision_model:
            logger.info(f"Processing {len(image_urls_to_process)} image URLs...")
            try:

                image_results = self.mamba_vision_model.get_features_batch(
                    image_urls_to_process
                )
                logger.info("Image batch processing complete.")
            except Exception as e:
                logger.error(
                    f"Error during MambaVision batch processing: {e}", exc_info=True
                )

                for url in image_urls_to_process:
                    if url not in final_results:
                        final_results[url] = {
                            "url": url,
                            "status": STATUS_FAILED_PROCESSING,
                            "feature_vector": None,
                            "error_message": f"Image batch processing error: {e}",
                        }

        audio_results: Dict[str, Optional[np.ndarray]] = {}
        if audio_urls_to_process and self.clap_model:
            logger.info(f"Processing {len(audio_urls_to_process)} audio URLs...")
            try:

                audio_results = self.clap_model.get_features_batch(
                    audio_urls_to_process
                )
                logger.info("Audio batch processing complete.")
            except Exception as e:
                logger.error(f"Error during CLAP batch processing: {e}", exc_info=True)

                for url in audio_urls_to_process:
                    if url not in final_results:
                        final_results[url] = {
                            "url": url,
                            "status": STATUS_FAILED_PROCESSING,
                            "feature_vector": None,
                            "error_message": f"Audio batch processing error: {e}",
                        }

        logger.info("Aggregating final results...")
        output_list: List[Dict[str, Any]] = []
        for url in url_map.keys():
            if url in final_results:
                output_list.append(final_results[url])
                continue

            result_data = None
            media_type = url_map[url]

            if media_type == MEDIA_TYPE_IMAGE:
                result_data = image_results.get(url)
            elif media_type == MEDIA_TYPE_AUDIO:
                result_data = audio_results.get(url)

            status = (
                STATUS_SUCCESS if result_data is not None else STATUS_FAILED_PROCESSING
            )
            error_msg = (
                None
                if status == STATUS_SUCCESS
                else "Processing failed (download or model internal error)."
            )

            final_results[url] = {
                "url": url,
                "status": status,
                "feature_vector": result_data,
                "error_message": error_msg,
            }
            output_list.append(final_results[url])

        logger.info(
            f"Extractor finished processing. Returning {len(output_list)} results."
        )
        return output_list


if __name__ == "__main__":
    print("--- Extractor Example Usage ---")

    try:
        extractor = Extractor(device="cuda" if torch.cuda.is_available() else "cpu")

        test_items = [
            {
                "url": "https://images.pexels.com/photos/20787/pexels-photo.jpg?auto=compress&cs=tinysrgb&dpr=1&w=500",
                "type": MEDIA_TYPE_IMAGE,
            },
            {
                "url": "https://github.com/karolpiczak/ESC-50/raw/master/audio/1-100032-A-0.wav",
                "type": MEDIA_TYPE_AUDIO,
            },
            {"url": "http://inv.alid.url/image.jpg", "type": MEDIA_TYPE_IMAGE},
            {"url": "https://www.google.com", "type": MEDIA_TYPE_IMAGE},
            {"url": "https://some.domain/file.txt", "type": MEDIA_TYPE_UNKNOWN},
            {
                "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
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
