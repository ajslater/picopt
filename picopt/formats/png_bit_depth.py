#!/usr/bin/env python3
"""get the bit depth of a png imagg"""

PNG_HEADER = (137, 80, 78, 71, 13, 10, 26, 10)


def png_bit_depth(filename):
    with open(filename, 'rb') as img:
        img.seek(0)
        header = tuple(img.read(8))
        if header != PNG_HEADER:
            print('not a png!')
            return

        img.seek(24)  # bit depth offset
        return tuple(img.read(1))[0]


def main(filename):
    bit_depth = png_bit_depth(filename)
    print(bit_depth)


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
