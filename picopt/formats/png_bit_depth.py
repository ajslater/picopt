#!/usr/bin/env python3
"""get the bit depth of a png image manually."
   This should really be a part of Pillow
"""
import struct

PNG_HEADER = (b'\x89', b'P', b'N', b'G', b'\r', b'\n', b'\x1a', b'\n')


def unpack(fmt_type, length, file_desc):
    """unpack unformation from a file according to format string & length"""
    return struct.unpack(fmt_type*length, file_desc.read(length))


def png_bit_depth(filename):
    """if a file is a png, get the bit depth from the standard position."""
    with open(filename, 'rb') as img:
        img.seek(0)
        header = unpack('c', 8, img)
        if header != PNG_HEADER:
            print(filename, 'is not a png!')
            return

        img.seek(24)  # bit depth offset
        depth = unpack('b', 1, img)[0]
        return depth


def main(filename):
    """stand alone cli tool for getting png bit depth."""
    bit_depth = png_bit_depth(filename)
    print(bit_depth)


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
