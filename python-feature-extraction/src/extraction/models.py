import torch
from transformers import AutoModel
from transformers import ClapModel, ClapProcessor
from PIL import Image
from timm.data.transforms_factory import create_transform
import requests
from io import BytesIO
import soundfile as sf
import librosa
from typing import List, Dict, Optional, Tuple
import numpy as np
from processing.audio import denoise_audio_spectral_gate
from processing.image import denoise_image_bilateral, denoise_image_nlm

import logging

logger = logging.getLogger(__name__)


class MambaVisionModel:

    DEFAULT_INPUT_RES = (3, 256, 256)
    REQUESTS_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def __init__(
        self,
        model_name="nvidia/MambaVision-L2-512-21K",
        input_res: Optional[Tuple[int, int, int]] = None,
        device: Optional[str] = None,
    ):
        """
        Initializes the MambaVision model and transformation pipeline.

        Args:
            model_name: The name of the model on Hugging Face Hub.
            input_res: The expected input resolution (C, H, W). Uses DEFAULT_INPUT_RES if None.
            device: The device to run the model on ('cuda', 'cpu', or specific cuda device like 'cuda:0').
                    Auto-detects CUDA if None.
        """
        print(f"Initializing MambaVisionModel with model: {model_name}")

        self.input_res = input_res if input_res is not None else self.DEFAULT_INPUT_RES
        if len(self.input_res) != 3:
            raise ValueError("input_res must be a tuple of (Channels, Height, Width)")

        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self.model.to(self.device)
        self.model.eval()

        self.transform = create_transform(
            input_size=self.input_res,
            is_training=False,
            mean=getattr(self.model.config, "mean", (0.485, 0.456, 0.406)),
            std=getattr(self.model.config, "std", (0.229, 0.224, 0.225)),
            crop_mode=getattr(self.model.config, "crop_mode", "squash"),
            crop_pct=getattr(self.model.config, "crop_pct", 1.0),
        )
        print("Model and transform ready.")

    @torch.inference_mode()
    def get_features_batch(
        self, input_img_urls: List[str], apply_denoise: bool = True
    ) -> Dict[str, Optional[np.ndarray]]:
        """
        Downloads images from URLs, preprocesses them, extracts features in a batch,
        and returns a dictionary mapping original URLs to their feature vectors (or None if processing failed).

        Args:
            input_img_urls: A list of URLs pointing to images.

        Returns:
            A dictionary where keys are the input URLs and values are the
            corresponding feature vectors as NumPy arrays (shape: [feature_dim]),
            or None if an image could not be processed.
        """
        processed_tensors = []
        url_order = []
        results = {url: None for url in input_img_urls}

        for url in input_img_urls:
            try:
                response = requests.get(
                    url, stream=True, timeout=10, headers=self.REQUESTS_HEADERS
                )
                response.raise_for_status()

                image = Image.open(BytesIO(response.content)).convert("RGB")

                if apply_denoise:
                    logger.debug(f"Applying denoising to image from {url}")
                    image = denoise_image_bilateral(image)

                input_tensor = self.transform(image)
                processed_tensors.append(input_tensor)
                url_order.append(url)

            except requests.exceptions.RequestException as e:
                print(f"Error downloading {url}: {e}")
            except (IOError, Image.UnidentifiedImageError) as e:
                print(f"Error opening or processing image {url}: {e}")
            except Exception as e:
                print(f"Unexpected error processing {url}: {e}")

        if not processed_tensors:
            print("No images could be processed successfully.")
            return results

        try:
            batch_tensor = torch.stack(processed_tensors).to(self.device)
            print(f"Processing batch of size: {batch_tensor.size(0)}")
        except Exception as e:
            print(f"Error stacking tensors: {e}")

            return results

        try:

            batch_features, _ = self.model(batch_tensor)

            feature_vectors_np = batch_features.detach().cpu().numpy()

            for i, url in enumerate(url_order):
                results[url] = feature_vectors_np[i]

        except Exception as e:
            print(f"Error during model inference or feature processing: {e}")

        return results

    def get_features_batch_from_bytes(
        self, image_bytes_list: List[bytes], apply_denoise: bool = True
    ) -> List[Optional[np.ndarray]]:
        processed_tensors = []
        results = {f"uploaded_image_{i}": None for i in range(len(image_bytes_list))}

        for image_bytes in image_bytes_list:
            try:
                image = Image.open(BytesIO(image_bytes)).convert("RGB")

                if apply_denoise:
                    logger.debug(f"Applying denoising to image from {url}")
                    image = denoise_image_bilateral(image)

                input_tensor = self.transform(image)
                processed_tensors.append(input_tensor)

            except (IOError, Image.UnidentifiedImageError) as e:
                print(f"Error opening or processing image {url}: {e}")
            except Exception as e:
                print(f"Unexpected error processing {url}: {e}")

        if not processed_tensors:
            print("No images could be processed successfully.")
            return results

        try:
            batch_tensor = torch.stack(processed_tensors).to(self.device)
            print(f"Processing batch of size: {batch_tensor.size(0)}")
        except Exception as e:
            print(f"Error stacking tensors: {e}")

            return results

        try:

            batch_features, _ = self.model(batch_tensor)

            feature_vectors_np = batch_features.detach().cpu().numpy()

            for i in range(len(image_bytes_list)):
                results[f"uploaded_image{i}"] = feature_vectors_np[i]

        except Exception as e:
            print(f"Error during model inference or feature processing: {e}")

        return results


class CLAPModel:

    DEFAULT_MODEL_NAME = "laion/larger_clap_general"
    DEFAULT_PROCESSOR_NAME = "laion/larger_clap_general"

    REQUESTS_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        processor_name: str = DEFAULT_PROCESSOR_NAME,
        device: Optional[str] = None,
    ):
        """
        Initializes the CLAP model and processor.

        Args:
            model_name: The name of the CLAP model on Hugging Face Hub.
            processor_name: The name of the CLAP processor on Hugging Face Hub.
            device: The device to run the model on ('cuda', 'cpu', or specific cuda device like 'cuda:0').
                    Auto-detects CUDA if None.
        """
        print(
            f"Initializing CLAPModel with model: {model_name}, processor: {processor_name}"
        )

        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        try:
            self.model = ClapModel.from_pretrained(model_name).to(self.device)
            self.processor = ClapProcessor.from_pretrained(processor_name)
            self.target_sampling_rate = self.processor.feature_extractor.sampling_rate
            print(f"Target sampling rate: {self.target_sampling_rate}")
        except Exception as e:
            print(f"Error loading model/processor: {e}")
            raise

        self.model.eval()
        print("CLAP Model and processor ready.")

    @torch.inference_mode()
    def get_features_batch(
        self, input_audio_urls: List[str], apply_denoise: bool = True
    ) -> Dict[str, Optional[np.ndarray]]:
        """
        Downloads audio from URLs, preprocesses them using the CLAP processor,
        extracts audio features (embeddings) in a batch, and returns a dictionary
        mapping original URLs to their feature vectors (or None if processing failed).

        Args:
            input_audio_urls: A list of URLs pointing to audio files (e.g., .wav, .mp3).

        Returns:
            A dictionary where keys are the input URLs and values are the
            corresponding audio feature vectors as NumPy arrays (shape: [feature_dim]),
            or None if an audio file could not be processed.
        """
        raw_audio_data = []
        url_order = []
        results = {url: None for url in input_audio_urls}

        for url in input_audio_urls:
            try:
                print(f"Processing URL: {url}")
                response = requests.get(
                    url, stream=True, timeout=15, headers=self.REQUESTS_HEADERS
                )
                response.raise_for_status()

                audio_waveform, original_sr = librosa.load(
                    BytesIO(response.content), sr=None, mono=True
                )

                if original_sr != self.target_sampling_rate:
                    print(
                        f"Resampling {url} from {original_sr} Hz to {self.target_sampling_rate} Hz"
                    )
                    audio_waveform = librosa.resample(
                        audio_waveform,
                        orig_sr=original_sr,
                        target_sr=self.target_sampling_rate,
                    )

                if apply_denoise:
                    logger.debug(f"Applying denoising to audio from {url}")
                    audio_waveform = denoise_audio_spectral_gate(
                        audio_waveform, sampling_rate=self.target_sampling_rate
                    )

                raw_audio_data.append(audio_waveform)
                url_order.append(url)
                print(f"Successfully loaded and preprocessed: {url}")

            except requests.exceptions.RequestException as e:
                print(f"Error downloading {url}: {e}")
            except (sf.SoundFileError, RuntimeError, TypeError, ValueError) as e:

                print(f"Error loading/processing audio data from {url}: {e}")
            except Exception as e:
                print(f"Unexpected error processing {url}: {e}")

        if not raw_audio_data:
            print("No audio files could be processed successfully.")
            return results

        try:
            print(f"Processing batch of size: {len(raw_audio_data)}")

            inputs = self.processor(
                audios=raw_audio_data,
                return_tensors="pt",
                sampling_rate=self.target_sampling_rate,
                padding=True,
            )

            inputs = inputs.to(self.device)
            print("Batch processed by CLAP processor.")

        except Exception as e:
            print(f"Error during CLAP processing stage: {e}")

            return results

        try:
            print("Extracting features using CLAP model...")

            audio_features = self.model.get_audio_features(**inputs)
            print(f"Extracted features shape: {audio_features.shape}")

            feature_vectors_np = audio_features.detach().cpu().numpy()

            for i, url in enumerate(url_order):
                results[url] = feature_vectors_np[i]
            print("Mapped features back to URLs.")

        except Exception as e:
            print(f"Error during model inference or feature post-processing: {e}")

        return results

    def get_features_batch_from_bytes(
        self, audio_bytes_list: List[bytes], apply_denoise: bool = True
    ) -> List[Optional[np.ndarray]]:
        raw_audio_data = []
        results = {f"uploaded_audio{i}": None for i in range(len(audio_bytes_list))}

        for audio_bytes in audio_bytes_list:
            try:

                audio_waveform, original_sr = librosa.load(
                    BytesIO(audio_bytes), sr=None, mono=True
                )

                if original_sr != self.target_sampling_rate:
                    print(
                        f"Resampling {url} from {original_sr} Hz to {self.target_sampling_rate} Hz"
                    )
                    audio_waveform = librosa.resample(
                        audio_waveform,
                        orig_sr=original_sr,
                        target_sr=self.target_sampling_rate,
                    )

                if apply_denoise:
                    logger.debug(f"Applying denoising to audio from {url}")
                    audio_waveform = denoise_audio_spectral_gate(
                        audio_waveform, sampling_rate=self.target_sampling_rate
                    )

                raw_audio_data.append(audio_waveform)
                print(f"Successfully loaded and preprocessed: {url}")

            except (sf.SoundFileError, RuntimeError, TypeError, ValueError) as e:

                print(f"Error loading/processing audio data from {url}: {e}")
            except Exception as e:
                print(f"Unexpected error processing {url}: {e}")

        if not raw_audio_data:
            print("No audio files could be processed successfully.")
            return results

        try:
            print(f"Processing batch of size: {len(raw_audio_data)}")

            inputs = self.processor(
                audios=raw_audio_data,
                return_tensors="pt",
                sampling_rate=self.target_sampling_rate,
                padding=True,
            )

            inputs = inputs.to(self.device)
            print("Batch processed by CLAP processor.")

        except Exception as e:
            print(f"Error during CLAP processing stage: {e}")

            return results

        try:
            print("Extracting features using CLAP model...")

            audio_features = self.model.get_audio_features(**inputs)
            print(f"Extracted features shape: {audio_features.shape}")

            feature_vectors_np = audio_features.detach().cpu().numpy()

            for i in range(len(audio_bytes_list)):
                results[f"uploaded_audio_{i}"] = feature_vectors_np[i]
            print("Mapped features back to URLs.")

        except Exception as e:
            print(f"Error during model inference or feature post-processing: {e}")

        return results


if __name__ == "__main__":
    print("--- MambaVision Example Usage ---")
    processor = MambaVisionModel()

    image_urls = [
        "https://images.pexels.com/photos/20787/pexels-photo.jpg?auto=compress&cs=tinysrgb&dpr=1&w=500",
        "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
        "http://inv.alid.url/image.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Dialog-error.svg/2048px-Dialog-error.svg.png",
        "https://rawhubusercontent.com/pytorch/pytorch/main/README.md",
    ]

    extracted_features = processor.get_features_batch(image_urls)

    print("\n--- Extraction Results ---")
    for url, features in extracted_features.items():
        if features is not None:
            print(f"URL: {url}, Feature Vector Shape: {features.shape}")
        else:
            print(f"URL: {url}, Failed to extract features.")
    print("-" * 20)

    print("\n--- Processing another batch ---")
    more_urls = [
        "https://images.pexels.com/photos/876466/pexels-photo-876466.jpeg?auto=compress&cs=tinysrgb&w=600"
    ]
    more_features = processor.get_features_batch(more_urls)
    for url, features in more_features.items():
        if features is not None:
            print(f"URL: {url}, Feature Vector Shape: {features.shape}")
        else:
            print(f"URL: {url}, Failed to extract features.")
    print("-" * 20)

    print("--- CLAP Model Example Usage ---")

    clap_processor = CLAPModel()

    audio_urls = [
        "https://github.com/karolpiczak/ESC-50/raw/master/audio/1-100032-A-0.wav",
        "https://github.com/karolpiczak/ESC-50/raw/master/audio/1-100038-A-14.wav",
        "https://datasets-server.huggingface.co/assets/speechcolab/gigaspeech/--/default/test/53/audio.wav",
        "http://inv.alid.url/audio.wav",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    ]

    extracted_features = clap_processor.get_features_batch(audio_urls)

    print("\n--- Extraction Results ---")
    for url, features in extracted_features.items():
        if features is not None:

            print(f"URL: {url}, Feature Vector Shape: {features.shape}")
        else:
            print(f"URL: {url}, Failed to extract features.")
    print("-" * 20)
