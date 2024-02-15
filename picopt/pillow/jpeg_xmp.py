#!/usr/bin/env python
"""Get raw jpeg xml from Pillow."""
from PIL.JpegImagePlugin import JpegImageFile

APP1_SECTION_DELIMETER = b"\x00"
XAP_MARKER =  b"http://ns.adobe.com/xap/1.0/"
SOI_MARKER = b"\xFF\xD8"
EOI_MARKER = b"\xFF\xE1"

def get_jpeg_xmp(image: JpegImageFile) -> str | None:
    """Get raw jpeg xml from Pillow."""
    xmp = None
    # Copied from PIL JpegImageFile
    for segment, content in image.applist:  # type: ignore
        if segment == "APP1":
            sections = content.split(APP1_SECTION_DELIMETER)
            marker, xmp_tags = sections[:2]
            if marker == XAP_MARKER:
                xmp = xmp_tags.decode()
                break
    return xmp

def main(fn: str):
    """Test function with fn."""
    from PIL import Image

    with Image.open(fn) as image:
        xmp = get_jpeg_xmp(image) # type: ignore
    print(xmp) # noqa: T201

if __name__ == "__main__":
    import sys
    main(sys.argv[1])
