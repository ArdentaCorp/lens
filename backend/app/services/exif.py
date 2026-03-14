"""Extract EXIF metadata from images using Pillow."""
import logging
from pathlib import Path

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

logger = logging.getLogger(__name__)


def _dms_to_decimal(dms, ref: str) -> float:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def extract_exif(image_path: str) -> dict:
    """Extract useful EXIF fields from an image. Returns a flat dict."""
    path = Path(image_path)
    if not path.exists():
        return {}

    try:
        img = Image.open(path)
    except Exception as e:
        logger.debug("Cannot open image for EXIF: %s", e)
        return {}

    exif_data = img.getexif()
    if not exif_data:
        return {}

    result: dict = {}

    # Standard EXIF tags
    tag_map = {
        "Make": "camera_make",
        "Model": "camera_model",
        "DateTime": "datetime",
        "DateTimeOriginal": "datetime_original",
        "ImageWidth": "width",
        "ImageLength": "height",
        "ExifImageWidth": "width",
        "ExifImageHeight": "height",
        "Orientation": "orientation",
        "Software": "software",
        "LensModel": "lens_model",
        "FocalLength": "focal_length",
        "ExposureTime": "exposure_time",
        "FNumber": "f_number",
        "ISOSpeedRatings": "iso",
    }

    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, str(tag_id))
        if tag_name in tag_map:
            # Convert IFDRational to float
            if hasattr(value, "numerator"):
                value = float(value)
            result[tag_map[tag_name]] = value

    # GPS data (in IFD block 0x8825)
    gps_ifd = exif_data.get_ifd(0x8825)
    if gps_ifd:
        gps = {}
        for tag_id, value in gps_ifd.items():
            tag_name = GPSTAGS.get(tag_id, str(tag_id))
            gps[tag_name] = value

        try:
            if "GPSLatitude" in gps and "GPSLatitudeRef" in gps:
                result["gps_lat"] = _dms_to_decimal(
                    gps["GPSLatitude"], gps["GPSLatitudeRef"])
            if "GPSLongitude" in gps and "GPSLongitudeRef" in gps:
                result["gps_lon"] = _dms_to_decimal(
                    gps["GPSLongitude"], gps["GPSLongitudeRef"])
            if "GPSAltitude" in gps:
                alt = float(gps["GPSAltitude"])
                if gps.get("GPSAltitudeRef", 0) == 1:
                    alt = -alt
                result["gps_alt"] = alt
        except Exception as e:
            logger.debug("GPS parsing error: %s", e)

    # Also get image dimensions from PIL if not in EXIF
    if "width" not in result or "height" not in result:
        result["width"] = img.width
        result["height"] = img.height

    img.close()
    return result
