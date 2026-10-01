# -*- coding: utf-8 -*-
import base64
import binascii
import os
import random
from flask import Flask, render_template, request
from PIL import Image

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

DIST = 8

# ----------------- AES ENCRYPTION / DECRYPTION -----------------


def get_aes_key(key_text):
    return key_text.encode('utf-8').ljust(16, b'0')[:16]


def aes_encrypt(plain_text, key_text):
    if not HAS_CRYPTO or not key_text:
        return plain_text
    key = get_aes_key(key_text)
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plain_text.encode('utf-8'), AES.block_size))
    return base64.b64encode(cipher.iv + ct_bytes).decode('utf-8')


def aes_decrypt(cipher_text, key_text):
    if not HAS_CRYPTO or not key_text:
        return cipher_text
    try:
        raw = base64.b64decode(cipher_text.encode('utf-8'))
        iv = raw[:16]
        ct = raw[16:]
        key = get_aes_key(key_text)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt.decode('utf-8')
    except Exception:
        return "DECRYPTION FAILED: Invalid Secret Key or Corrupted Data!"


# ----------------- STEGANOGRAPHY CORE -----------------


def _normalize(i):
    return i - 1 if i >= 128 else i + 1


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
    return i


def is_modify_pixel(r, g, b):
    return (r % DIST == 1) and (g % DIST == 1) and (b % DIST == 1)


def normalize_pixel(r, g, b):
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
    return tuple(map(_modify, [r, g, b]))


def normalize(path, output):
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
    try:
        return binascii.unhexlify(s).decode()
    except Exception:
        return ""


def hide_text(path, text):
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


# ----------------- ROUTES -----------------


@app.route('/')
def index():
    return render_template('index.html', active_tab='encode')


@app.route('/encode', methods=['POST'])
def encode():
    cover = request.files['cover_image']
    key = request.form['secret_key']
    patient_data = request.form['patient_data']

    input_path = os.path.join(app.config['UPLOAD_FOLDER'], 'original_' + cover.filename)
    cover.save(input_path)

    # 1. AES Encrypt the data
    encrypted_data = aes_encrypt(patient_data, key)

    # 2. Hide encrypted data in image
    stego_filename = 'stego_' + os.path.splitext(cover.filename)[0] + '.png'
    stego_path = os.path.join('static', stego_filename)

    normalize(input_path, stego_path)
    hide_text(stego_path, encrypted_data)

    return render_template(
        'index.html',
        active_tab='encode',
        encode_success=True,
        stego_url='/' + stego_path,
    )


@app.route('/decode', methods=['POST'])
def decode():
    stego_file = request.files['stego_image']
    key = request.form['secret_key']

    stego_path = os.path.join(app.config['UPLOAD_FOLDER'], 'recv_' + stego_file.filename)
    stego_file.save(stego_path)

    # 1. Extract hidden ciphertext from image
    extracted_cipher = read_text(stego_path)

    # 2. Decrypt with AES Key
    decrypted_text = aes_decrypt(extracted_cipher, key)

    return render_template(
        'index.html',
        active_tab='decode',
        decoded_data=decrypted_text,
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)