import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    import noisereduce as nr

    NOISEREDUCE_AVAILABLE = True
except ImportError:
    logger.warning(
        "noisereduce not found. Audio denoising function will not be available."
    )
    NOISEREDUCE_AVAILABLE = False


def denoise_audio_spectral_gate(
    audio_waveform: np.ndarray, sampling_rate: int, **kwargs
) -> np.ndarray:
    """
    Applies spectral gating noise reduction using the noisereduce library.

    Args:
        audio_waveform: NumPy array of the audio time series.
        sampling_rate: Sampling rate of the audio.
        **kwargs: Additional keyword arguments passed directly to
                  noisereduce.reduce_noise (e.g., n_std_thresh_stationary, prop_decrease).

    Returns:
        Denoised NumPy array waveform, or the original waveform if noisereduce is not available.
    """
    if not NOISEREDUCE_AVAILABLE:
        logger.warning("noisereduce not available, skipping spectral gate denoising.")
        return audio_waveform

    if audio_waveform is None or audio_waveform.size == 0:
        logger.warning("Input audio waveform is empty, skipping denoising.")
        return audio_waveform

    try:

        if not np.issubdtype(audio_waveform.dtype, np.floating):
            audio_waveform = audio_waveform.astype(np.float32)

        reduced_noise_waveform = nr.reduce_noise(
            y=audio_waveform, sr=sampling_rate, **kwargs
        )
        logger.debug("Applied spectral gate denoising to audio.")
        return reduced_noise_waveform
    except Exception as e:
        logger.error(f"Error during spectral gate denoising: {e}")
        return audio_waveform


if __name__ == "__main__":

    print("\n--- Audio Denoising Example (Requires noisereduce & librosa) ---")
    if NOISEREDUCE_AVAILABLE:
        try:
            import librosa

            sr_test = 16000
            duration = 5
            signal = np.sin(2 * np.pi * 440.0 * np.arange(sr_test * duration) / sr_test)
            noise = np.random.randn(len(signal)) * 0.1
            noisy_signal = signal + noise

            print("Attempting Spectral Gate Denoising...")
            denoised_audio = denoise_audio_spectral_gate(noisy_signal, sr_test)

            print(
                f"Spectral Gate applied. Original length: {len(noisy_signal)}, Denoised length: {len(denoised_audio)}"
            )

        except ImportError:
            print(
                "Skipping audio denoising example: librosa (for dummy data) not installed."
            )
        except Exception as e:
            print(f"Error running audio denoising example: {e}")

    else:
        print("Skipping audio denoising example: noisereduce not installed.")
