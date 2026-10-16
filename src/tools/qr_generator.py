"""ISO/IEC 18004 QR Code Matrix & SVG Generator (`src/tools/qr_generator.py`).

Generates standard-compliant, phone-camera-scannable ISO/IEC 18004 QR Code matrices
and SVG graphics (Byte mode, Error Correction Level L, Versions 1-10) with zero
external runtime dependencies or network calls.
"""

from __future__ import annotations

import html
from typing import List, Tuple

# Version 1..10 specs for Error Correction Level L:
# (total_codewords, ec_codewords_per_block, num_blocks_group1, data_codewords_group1,
#  num_blocks_group2, data_codewords_group2, alignment_centers)
_QR_VERSION_SPECS_L: dict[int, Tuple[int, int, int, int, int, int, Tuple[int, ...]]] = {
    1: (26, 7, 1, 19, 0, 0, ()),
    2: (44, 10, 1, 34, 0, 0, (6, 18)),
    3: (70, 15, 1, 55, 0, 0, (6, 22)),
    4: (100, 20, 1, 80, 0, 0, (6, 26)),
    5: (134, 26, 1, 108, 0, 0, (6, 30)),
    6: (172, 18, 2, 68, 0, 0, (6, 34)),
    7: (196, 20, 2, 78, 0, 0, (6, 22, 38)),
    8: (242, 24, 2, 97, 0, 0, (6, 24, 42)),
    9: (292, 30, 2, 116, 0, 0, (6, 26, 46)),
    10: (346, 18, 2, 68, 2, 69, (6, 28, 50)),
}

# Precomputed 15-bit Format Information strings for Error Correction Level L (01) and Mask 0..7
_FORMAT_BITS_L: Tuple[int, ...] = (
    0x77C4,  # Mask 0
    0x72F3,  # Mask 1
    0x7DAA,  # Mask 2
    0x789D,  # Mask 3
    0x662F,  # Mask 4
    0x6318,  # Mask 5
    0x6C41,  # Mask 6
    0x6976,  # Mask 7
)

# Precomputed 18-bit Version Information for Versions 7..10
_VERSION_BITS: dict[int, int] = {
    7: 0x07C94,
    8: 0x085BC,
    9: 0x09A99,
    10: 0x0A4D3,
}


def _gf_tables() -> Tuple[List[int], List[int]]:
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_GF_EXP, _GF_LOG = _gf_tables()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator_poly(degree: int) -> List[int]:
    poly = [1]
    for i in range(degree):
        next_poly = [0] * (len(poly) + 1)
        factor = _GF_EXP[i]
        for j, coeff in enumerate(poly):
            next_poly[j] ^= coeff
            next_poly[j + 1] ^= _gf_mul(coeff, factor)
        poly = next_poly
    return poly


def _rs_encode(data: List[int], ec_len: int) -> List[int]:
    gen = _rs_generator_poly(ec_len)
    rem = [0] * ec_len
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor != 0:
            for j in range(ec_len):
                rem[j] ^= _gf_mul(gen[j + 1], factor)
    return rem


def encode_qr_matrix(text: str) -> List[List[bool]]:
    """Encodes `text` into a 2D boolean matrix representing an ISO/IEC 18004 QR Code."""
    payload_bytes = list((text or "https://www.scouting.org").encode("utf-8"))
    version = 10
    for v in range(1, 11):
        spec = _QR_VERSION_SPECS_L[v]
        data_cap = spec[2] * spec[3] + spec[4] * spec[5]
        len_bits = 8 if v <= 9 else 16
        max_bytes = ((data_cap * 8) - 4 - len_bits) // 8
        if len(payload_bytes) <= max_bytes:
            version = v
            break
    else:
        # Truncate if longer than Version 10 capacity (271 bytes)
        payload_bytes = payload_bytes[:270]

    total_cw, ec_len, g1_blocks, g1_data, g2_blocks, g2_data, align_centers = _QR_VERSION_SPECS_L[version]
    data_capacity = g1_blocks * g1_data + g2_blocks * g2_data
    len_bits = 8 if version <= 9 else 16

    # Build bit stream: 0100 (Byte mode) + character count + payload bytes + terminator + pad
    bits: List[int] = [0, 1, 0, 0]
    for i in range(len_bits - 1, -1, -1):
        bits.append((len(payload_bytes) >> i) & 1)
    for b in payload_bytes:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)

    max_bits = data_capacity * 8
    term_len = min(4, max_bits - len(bits))
    bits.extend([0] * term_len)
    while len(bits) % 8 != 0:
        bits.append(0)

    data_codewords: List[int] = []
    for i in range(0, len(bits), 8):
        val = 0
        for bit in bits[i : i + 8]:
            val = (val << 1) | bit
        data_codewords.append(val)

    pad_bytes = (0xEC, 0x11)
    pad_idx = 0
    while len(data_codewords) < data_capacity:
        data_codewords.append(pad_bytes[pad_idx % 2])
        pad_idx += 1

    # Split into blocks and compute Reed-Solomon EC codewords
    blocks_data: List[List[int]] = []
    blocks_ec: List[List[int]] = []
    offset = 0
    for _ in range(g1_blocks):
        blk = data_codewords[offset : offset + g1_data]
        offset += g1_data
        blocks_data.append(blk)
        blocks_ec.append(_rs_encode(blk, ec_len))
    for _ in range(g2_blocks):
        blk = data_codewords[offset : offset + g2_data]
        offset += g2_data
        blocks_data.append(blk)
        blocks_ec.append(_rs_encode(blk, ec_len))

    # Interleave data and EC codewords
    interleaved: List[int] = []
    max_data_len = max(g1_data, g2_data)
    for col in range(max_data_len):
        for blk in blocks_data:
            if col < len(blk):
                interleaved.append(blk[col])
    for col in range(ec_len):
        for ec_blk in blocks_ec:
            interleaved.append(ec_blk[col])

    final_bits: List[int] = []
    for cw in interleaved:
        for i in range(7, -1, -1):
            final_bits.append((cw >> i) & 1)
    # Remainder bits (7 for V2..6, 0 for V1 and V7..10)
    if 2 <= version <= 6:
        final_bits.extend([0] * 7)

    size = 17 + 4 * version
    modules: List[List[bool]] = [[False] * size for _ in range(size)]
    is_func: List[List[bool]] = [[False] * size for _ in range(size)]

    def set_func(r: int, c: int, val: bool) -> None:
        if 0 <= r < size and 0 <= c < size:
            modules[r][c] = val
            is_func[r][c] = True

    def draw_finder(r0: int, c0: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r0 + dr, c0 + dc
                if 0 <= rr < size and 0 <= cc < size:
                    in_square = 0 <= dr <= 6 and 0 <= dc <= 6
                    is_dark = in_square and (
                        dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)
                    )
                    set_func(rr, cc, is_dark)

    draw_finder(0, 0)
    draw_finder(0, size - 7)
    draw_finder(size - 7, 0)

    # Timing patterns
    for i in range(8, size - 8):
        set_func(6, i, i % 2 == 0)
        set_func(i, 6, i % 2 == 0)

    # Alignment patterns
    for r_c in align_centers:
        for c_c in align_centers:
            if (r_c == 6 and c_c == 6) or (r_c == 6 and c_c == size - 7) or (r_c == size - 7 and c_c == 6):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    is_dark = max(abs(dr), abs(dc)) in (0, 2)
                    set_func(r_c + dr, c_c + dc, is_dark)

    # Dark module & reserve format areas
    set_func(size - 8, 8, True)
    for i in range(9):
        if not is_func[8][i]:
            set_func(8, i, False)
        if not is_func[i][8]:
            set_func(i, 8, False)
    for i in range(8):
        if not is_func[8][size - 1 - i]:
            set_func(8, size - 1 - i, False)
        if not is_func[size - 1 - i][8]:
            set_func(size - 1 - i, 8, False)

    # Version info for V7..10
    if version in _VERSION_BITS:
        vbits = _VERSION_BITS[version]
        for i in range(18):
            bit = ((vbits >> i) & 1) == 1
            a = size - 11 + (i % 3)
            b = i // 3
            set_func(a, b, bit)
            set_func(b, a, bit)

    # Place data bits in upward/downward 2-column zig-zag
    bit_idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        row_iter = range(size - 1, -1, -1) if upward else range(size)
        for r in row_iter:
            for dc in (0, 1):
                c = col - dc
                if not is_func[r][c]:
                    val = final_bits[bit_idx] == 1 if bit_idx < len(final_bits) else False
                    bit_idx += 1
                    # Apply Mask 0: (r + c) % 2 == 0
                    if (r + c) % 2 == 0:
                        val = not val
                    modules[r][c] = val
        upward = not upward
        col -= 2

    # Write Format Information for Mask 0
    fbits = _FORMAT_BITS_L[0]
    for i in range(6):
        set_func(8, i, ((fbits >> i) & 1) == 1)
    set_func(8, 7, ((fbits >> 6) & 1) == 1)
    set_func(8, 8, ((fbits >> 7) & 1) == 1)
    set_func(7, 8, ((fbits >> 8) & 1) == 1)
    for i in range(9, 15):
        set_func(14 - i, 8, ((fbits >> i) & 1) == 1)

    for i in range(8):
        set_func(size - 1 - i, 8, ((fbits >> i) & 1) == 1)
    for i in range(8, 15):
        set_func(8, size - 15 + i, ((fbits >> i) & 1) == 1)

    return modules


def render_qr_svg(url: str, size_px: int = 96, fg_color: str = "#003F87", bg_color: str = "#FFFFFF") -> str:
    """Renders an ISO/IEC 18004 QR Code for `url` as a self-contained SVG string."""
    matrix = encode_qr_matrix(url)
    n = len(matrix)
    quiet = 2
    total_modules = n + quiet * 2
    path_parts: List[str] = []
    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                path_parts.append(f"M{c + quiet},{r + quiet}h1v1h-1z")
    safe_label = html.escape(url, quote=True)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_px}" height="{size_px}" '
        f'viewBox="0 0 {total_modules} {total_modules}" shape-rendering="crispEdges" '
        f'role="img" aria-label="QR Code for {safe_label}">'
        f'<rect width="{total_modules}" height="{total_modules}" fill="{bg_color}"/>'
        f'<path d="{"".join(path_parts)}" fill="{fg_color}"/>'
        f"</svg>"
    )
