"""Get raw jpeg xml from Pillow."""
from PIL.JpegImagePlugin import JpegImageFile


def get_jpeg_xmp(image: JpegImageFile) -> str | None:
    """Get raw jpeg xml from Pillow."""
    xmp = None
    # Copied from PIL JpegImageFile
    for segment, content in image.applist:  # type: ignore
        if segment == "APP1":
            marker, xmp_tags = content.split(b"\x00")[:2]
            if marker == b"http://ns.adobe.com/xap/1.0/":
                xmp = xmp_tags
                break
    return xmp
