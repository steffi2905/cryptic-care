# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import binascii
import random
import cv2
from PIL import Image

DIST = 8


def _normalize(i):
    if i >= 128:
        i -= 1
    else:
        i += 1
    return i


def _modify(i):
    if i >= 128:
        for _ in range(DIST + 1):
            if i % DIST == 1:
                return i
            i -= 1
    else:
        for _ in range(DIST + 1):
            if i % DIST == 1:
                return i
            i += 1
    raise ValueError("Pixel modification error")


def is_modify_pixel(r, g, b):
    return (r % DIST == 1) and (g % DIST == 1) and (b % DIST == 1)


def normalize_pixel(r, g, b):
    """Normalize pixel color so it does not match modification signature."""
    if is_modify_pixel(r, g, b):
        seed = random.randint(1, 3)
        if seed == 1:
            r = _normalize(r)
        elif seed == 2:
            g = _normalize(g)
        elif seed == 3:
            b = _normalize(b)
    return r, g, b


def modify_pixel(r, g, b):
    """Modify pixel color to embed bit."""
    return tuple(map(_modify, [r, g, b]))


def normalize(path, output):
    """Pre-process and normalize image."""
    img = Image.open(path).convert('RGB')
    size = img.size
    new_img = Image.new('RGB', size)

    for y in range(size[1]):
        for x in range(size[0]):
            r, g, b = img.getpixel((x, y))
            _r, _g, _b = normalize_pixel(r, g, b)
            new_img.putpixel((x, y), (_r, _g, _b))

    new_img.save(output, "PNG", optimize=True)


def to_hex(s):
    return binascii.hexlify(s.encode()).decode()


def to_str(s):
    return binascii.unhexlify(s).decode()


def hide_text(path, text):
    """Hide text into the normalized image."""
    text = str(text)
    write_param = []
    _base = 0

    for ch in to_hex(text):
        write_param.append(int(ch, 16) + _base)
        _base += 16

    img = Image.open(path)
    counter = 0

    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if counter in write_param:
                r, g, b = img.getpixel((x, y))
                r, g, b = modify_pixel(r, g, b)
                img.putpixel((x, y), (r, g, b))
            counter += 1

    img.save(path, "PNG", optimize=True)


def read_text(path):
    """Extract and read secret text from the stego-image."""
    img = Image.open(path)
    counter = 0
    result = []

    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if is_modify_pixel(r, g, b):
                result.append(counter)
            counter += 1
            if counter == 16:
                counter = 0

    hex_data = "".join([hex(val)[-1:] for val in result])
    return to_str(hex_data)


class Steganography(object):
    @classmethod
    def encode(cls, input_image_path, output_image_path, encode_text):
        normalize(input_image_path, output_image_path)
        hide_text(output_image_path, encode_text)
        assert read_text(output_image_path) == encode_text, "Verification failed"

    @classmethod
    def decode(cls, image_path):
        return read_text(image_path)


def main():
    print("--- CrypticCare Steganography System ---")
    input_image_path = input("Enter path to input image (e.g. input.jpg): ").strip()
    output_image_path = "output_stego.png"
    text = input("Please enter the patient/secret text to hide: ")

    # Show original
    orig_img = cv2.imread(input_image_path)
    if orig_img is not None:
        cv2.imshow("Original Image", orig_img)

    print("Encoding...")
    Steganography.encode(input_image_path, output_image_path, text)
    print("Finished! Saved as:", output_image_path)

    # Show output
    out_img = cv2.imread(output_image_path)
    if out_img is not None:
        cv2.imshow("Stego Output Image", out_img)

    extracted = Steganography.decode(output_image_path)
    print("\nDecoded Secret Text:", extracted)

    if orig_img is not None or out_img is not None:
        print("\nPress any key on the image window to close.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()