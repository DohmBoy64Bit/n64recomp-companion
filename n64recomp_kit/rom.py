from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from .util import atomic_write_bytes, read_bytes

MAGIC_Z64 = b"\x80\x37\x12\x40"
MAGIC_V64 = b"\x37\x80\x40\x12"
MAGIC_N64 = b"\x40\x12\x37\x80"

COUNTRY_CODES = {
    0x37: "Beta",
    0x41: "Asia",
    0x44: "Germany",
    0x45: "USA",
    0x46: "France",
    0x49: "Italy",
    0x4A: "Japan",
    0x50: "Europe",
    0x53: "Spain",
    0x55: "Australia",
    0x58: "Europe",
    0x59: "Europe",
}


@dataclass
class RomInfo:
    path: str
    size_bytes: int
    byte_order: str
    title: str
    entrypoint: str
    clock_rate: str
    release: str
    crc1: str
    crc2: str
    cartridge_id: str
    country_code: str
    country: str
    version: int
    bootcode_sha1: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect_byte_order(prefix: bytes) -> str:
    magic = prefix[:4]
    if magic == MAGIC_Z64:
        return "z64-big-endian"
    if magic == MAGIC_V64:
        return "v64-byte-swapped-16"
    if magic == MAGIC_N64:
        return "n64-little-endian-32"
    return "unknown"


def _swap_v64(data: bytes) -> bytes:
    out = bytearray(data)
    limit = len(out) - (len(out) % 2)
    for i in range(0, limit, 2):
        out[i], out[i + 1] = out[i + 1], out[i]
    return bytes(out)


def _swap_n64(data: bytes) -> bytes:
    out = bytearray(data)
    limit = len(out) - (len(out) % 4)
    for i in range(0, limit, 4):
        out[i : i + 4] = reversed(out[i : i + 4])
    return bytes(out)


def to_z64_bytes(data: bytes) -> tuple[bytes, str]:
    order = detect_byte_order(data[:4])
    if order == "z64-big-endian":
        return data, order
    if order == "v64-byte-swapped-16":
        converted = _swap_v64(data)
    elif order == "n64-little-endian-32":
        converted = _swap_n64(data)
    else:
        raise ValueError("unrecognized N64 ROM byte order; expected .z64, .v64, or .n64 magic")
    if converted[:4] != MAGIC_Z64:
        raise ValueError("byte-order conversion did not produce z64 magic")
    return converted, order


def convert_to_z64(src: str | Path, dst: str | Path, *, overwrite: bool = False) -> dict:
    src_p = Path(src)
    dst_p = Path(dst)
    if dst_p.exists() and not overwrite:
        raise FileExistsError(f"output exists: {dst_p}")
    data = read_bytes(src_p)
    converted, source_order = to_z64_bytes(data)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(dst_p, converted)
    return {
        "source": str(src_p),
        "output": str(dst_p),
        "source_byte_order": source_order,
        "output_byte_order": "z64-big-endian",
        "size_bytes": len(converted),
        "sha256": hashlib.sha256(converted).hexdigest(),
    }


def inspect_rom(path: str | Path) -> RomInfo:
    p = Path(path)
    data = read_bytes(p, max_bytes=0x1000)
    full_size = p.stat().st_size
    z64_header, source_order = to_z64_bytes(data)
    if len(z64_header) < 0x40:
        raise ValueError("file is too small to contain an N64 ROM header")
    title_raw = z64_header[0x20:0x34]
    title = title_raw.decode("ascii", errors="replace").rstrip(" \x00")
    country_value = z64_header[0x3E]
    bootcode = z64_header[0x40:0x1000]
    return RomInfo(
        path=str(p),
        size_bytes=full_size,
        byte_order=source_order,
        title=title,
        entrypoint=f"0x{int.from_bytes(z64_header[0x08:0x0C], 'big'):08X}",
        clock_rate=f"0x{int.from_bytes(z64_header[0x04:0x08], 'big'):08X}",
        release=f"0x{int.from_bytes(z64_header[0x0C:0x10], 'big'):08X}",
        crc1=f"0x{int.from_bytes(z64_header[0x10:0x14], 'big'):08X}",
        crc2=f"0x{int.from_bytes(z64_header[0x14:0x18], 'big'):08X}",
        cartridge_id=z64_header[0x3C:0x3E].decode("ascii", errors="replace"),
        country_code=f"0x{country_value:02X}",
        country=COUNTRY_CODES.get(country_value, "Unknown"),
        version=z64_header[0x3F],
        bootcode_sha1=hashlib.sha1(bootcode).hexdigest(),
    )


def format_rom_info(info: RomInfo) -> str:
    rows = [
        ("Path", info.path),
        ("Size", f"{info.size_bytes} bytes"),
        ("Byte order", info.byte_order),
        ("Title", info.title or "<blank>"),
        ("Entrypoint", info.entrypoint),
        ("Clock rate", info.clock_rate),
        ("Release", info.release),
        ("CRC1", info.crc1),
        ("CRC2", info.crc2),
        ("Cartridge ID", info.cartridge_id),
        ("Country", f"{info.country} ({info.country_code})"),
        ("Version", str(info.version)),
        ("Bootcode SHA1", info.bootcode_sha1),
    ]
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{k:<{width}} : {v}" for k, v in rows)
