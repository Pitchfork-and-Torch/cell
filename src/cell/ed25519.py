"""Ed25519 sign/verify (RFC 8032) with the Python standard library only.

Verification follows the public-domain Bernstein check, plus rejection of
non-canonical S (S >= L). No third-party crypto package.
"""

from __future__ import annotations

import hashlib

_B = 256
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _expmod(base: int, exp: int, mod: int) -> int:
    return pow(base, exp, mod)


def _inv(x: int) -> int:
    return _expmod(x, _Q - 2, _Q)


_D = -121665 * _inv(121666)
_I = _expmod(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = _expmod(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_By = 4 * _inv(5)
_Bx = _xrecover(_By)
_BPT = [_Bx % _Q, _By % _Q]


def _edwards(P: list[int], Q: list[int]) -> list[int]:
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2)
    return [x3 % _Q, y3 % _Q]


def _scalarmult(P: list[int], e: int) -> list[int]:
    Q = [0, 1]
    if e == 0:
        return Q
    for bit in bin(e)[2:]:
        Q = _edwards(Q, Q)
        if bit == "1":
            Q = _edwards(Q, P)
    return Q


def _encodeint(y: int) -> bytes:
    bits = [(y >> i) & 1 for i in range(_B)]
    return bytes([sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_B // 8)])


def _encodepoint(P: list[int]) -> bytes:
    x, y = P
    bits = [(y >> i) & 1 for i in range(_B - 1)] + [x & 1]
    return bytes([sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_B // 8)])


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _hint(m: bytes) -> int:
    h = _H(m)
    return sum(2**i * _bit(h, i) for i in range(2 * _B))


def _isoncurve(P: list[int]) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


def _decodeint(s: bytes) -> int:
    return sum(2**i * _bit(s, i) for i in range(_B))


def _decodepoint(s: bytes) -> list[int]:
    y = sum(2**i * _bit(s, i) for i in range(_B - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, _B - 1):
        x = _Q - x
    P = [x, y]
    if not _isoncurve(P):
        raise ValueError("point is not on the curve")
    return P


def _secret_scalar(seed: bytes) -> tuple[int, bytes]:
    h = _H(seed)
    a = 2 ** (_B - 2) + sum(2**i * _bit(h, i) for i in range(3, _B - 2))
    return a, h


def public_key(seed: bytes) -> bytes:
    a, _h = _secret_scalar(seed)
    return _encodepoint(_scalarmult(_BPT, a))


def sign(seed: bytes, message: bytes) -> bytes:
    a, h = _secret_scalar(seed)
    pk = _encodepoint(_scalarmult(_BPT, a))
    prefix = h[_B // 8 : _B // 4]
    r = _hint(prefix + message)
    R = _scalarmult(_BPT, r)
    S = (r + _hint(_encodepoint(R) + pk + message) * a) % _L
    return _encodepoint(R) + _encodeint(S)


def verify(public: bytes, signature: bytes, message: bytes) -> bool:
    if len(public) != _B // 8 or len(signature) != _B // 4:
        return False
    try:
        R = _decodepoint(signature[: _B // 8])
        A = _decodepoint(public)
        S = _decodeint(signature[_B // 8 : _B // 4])
    except (ValueError, ZeroDivisionError):
        return False
    if S >= _L:
        return False
    h = _hint(_encodepoint(R) + public + message) % _L
    try:
        left = _scalarmult(_BPT, S)
        right = _edwards(R, _scalarmult(A, h))
    except (ValueError, ZeroDivisionError):
        return False
    return left == right
