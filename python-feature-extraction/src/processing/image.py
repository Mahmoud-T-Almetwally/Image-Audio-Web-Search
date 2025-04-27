import numpy as np
from PIL import Image
import logging

logger = logging.getLogger(__name__)

try:
    import cv2

    OPENCV_AVAILABLE = True
except ImportError:
    logger.warning(
        "OpenCV (cv2) not found. Image denoising functions will not be available."
    )
    OPENCV_AVAILABLE = False


def denoise_image_bilateral(
    img: Image.Image, diameter: int = 9, sigma_color: int = 75, sigma_space: int = 75
) -> Image.Image:
    """
    Applies Bilateral Filter denoising to a PIL Image using OpenCV.

    Args:
        img: Input PIL Image object (RGB).
        diameter: Diameter of each pixel neighborhood.
        sigma_color: Filter sigma in the color space.
        sigma_space: Filter sigma in the coordinate space.

    Returns:
        Denoised PIL Image object, or the original image if OpenCV is not available.
    """
    if not OPENCV_AVAILABLE:
        logger.warning("OpenCV not available, skipping bilateral denoising.")
        return img

    try:

        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        denoised_img_cv = cv2.bilateralFilter(
            img_cv, diameter, sigma_color, sigma_space
        )

        denoised_img_pil = Image.fromarray(
            cv2.cvtColor(denoised_img_cv, cv2.COLOR_BGR2RGB)
        )
        logger.debug("Applied bilateral filter denoising to image.")
        return denoised_img_pil
    except Exception as e:
        logger.error(f"Error during bilateral filter denoising: {e}")
        return img


def denoise_image_nlm(
    img: Image.Image,
    h: float = 10,
    template_window_size: int = 7,
    search_window_size: int = 21,
) -> Image.Image:
    """
    Applies Non-Local Means denoising to a PIL Image using OpenCV.
    More computationally intensive than bilateral filter.

    Args:
        img: Input PIL Image object (RGB).
        h: Parameter regulating filter strength. Higher h removes more noise but blurs more.
        template_window_size: Size in pixels of the template patch used for comparison (odd number).
        search_window_size: Size in pixels of the window where template matching is done (odd number).

    Returns:
        Denoised PIL Image object, or the original image if OpenCV is not available.
    """
    if not OPENCV_AVAILABLE:
        logger.warning("OpenCV not available, skipping NLM denoising.")
        return img

    try:

        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        denoised_img_cv = cv2.fastNlMeansDenoisingColored(
            img_cv, None, h, h, template_window_size, search_window_size
        )

        denoised_img_pil = Image.fromarray(
            cv2.cvtColor(denoised_img_cv, cv2.COLOR_BGR2RGB)
        )
        logger.debug("Applied Non-Local Means denoising to image.")
        return denoised_img_pil
    except Exception as e:
        logger.error(f"Error during Non-Local Means denoising: {e}")
        return img
