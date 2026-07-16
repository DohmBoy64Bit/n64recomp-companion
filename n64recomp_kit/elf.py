from __future__ import annotations

import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from .util import read_bytes

ELF_MAGIC = b"\x7fELF"
EM_MIPS = 8
SHF_EXECINSTR = 0x4


@dataclass
class ElfSection:
    name: str
    address: str
    offset: str
    size: str
    flags: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ElfInfo:
    path: str
    elf_class: str
    endian: str
    machine: str
    machine_id: int
    entrypoint: str
    section_count: int
    executable_sections: list[ElfSection]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["executable_sections"] = [s.to_dict() for s in self.executable_sections]
        return data


def _cstring(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ""
    end = blob.find(b"\x00", offset)
    if end == -1:
        end = len(blob)
    return blob[offset:end].decode("utf-8", errors="replace")


def inspect_elf(path: str | Path) -> ElfInfo:
    p = Path(path)
    data = read_bytes(p)
    if len(data) < 0x34 or data[:4] != ELF_MAGIC:
        raise ValueError("not an ELF file")
    elf_class_byte = data[4]
    endian_byte = data[5]
    if elf_class_byte != 1:
        raise ValueError("only ELF32 files are supported by this inspector")
    if endian_byte == 1:
        endian_prefix = "<"
        endian_name = "little"
    elif endian_byte == 2:
        endian_prefix = ">"
        endian_name = "big"
    else:
        raise ValueError("ELF header has an invalid endian marker")
    header = struct.unpack_from(endian_prefix + "HHIIIIIHHHHHH", data, 0x10)
    (
        _e_type,
        e_machine,
        _e_version,
        e_entry,
        _e_phoff,
        e_shoff,
        _e_flags,
        _e_ehsize,
        _e_phentsize,
        _e_phnum,
        e_shentsize,
        e_shnum,
        e_shstrndx,
    ) = header
    machine_name = "MIPS" if e_machine == EM_MIPS else f"machine-{e_machine}"
    if e_shoff == 0 or e_shnum == 0:
        sections: list[ElfSection] = []
        sh_count = 0
    else:
        if e_shentsize < 40:
            raise ValueError("ELF section header size is too small for ELF32")
        if e_shoff + e_shentsize * e_shnum > len(data):
            raise ValueError("ELF section table extends past end of file")
        section_headers = []
        for idx in range(e_shnum):
            off = e_shoff + idx * e_shentsize
            sh = struct.unpack_from(endian_prefix + "IIIIIIIIII", data, off)
            section_headers.append(sh)
        shstr = b""
        if e_shstrndx < len(section_headers):
            shstr_header = section_headers[e_shstrndx]
            start = shstr_header[4]
            size = shstr_header[5]
            shstr = data[start : start + size]
        sections = []
        for sh in section_headers:
            sh_name, _sh_type, sh_flags, sh_addr, sh_offset, sh_size, *_rest = sh
            if sh_flags & SHF_EXECINSTR:
                sections.append(
                    ElfSection(
                        name=_cstring(shstr, sh_name) or "<unnamed>",
                        address=f"0x{sh_addr:08X}",
                        offset=f"0x{sh_offset:X}",
                        size=f"0x{sh_size:X}",
                        flags=f"0x{sh_flags:X}",
                    )
                )
        sh_count = e_shnum
    return ElfInfo(
        path=str(p),
        elf_class="ELF32",
        endian=endian_name,
        machine=machine_name,
        machine_id=e_machine,
        entrypoint=f"0x{e_entry:08X}",
        section_count=sh_count,
        executable_sections=sections,
    )


def format_elf_info(info: ElfInfo) -> str:
    lines = [
        f"Path          : {info.path}",
        f"Class         : {info.elf_class}",
        f"Endian        : {info.endian}",
        f"Machine       : {info.machine} ({info.machine_id})",
        f"Entrypoint    : {info.entrypoint}",
        f"Sections      : {info.section_count}",
        f"Executable sections: {len(info.executable_sections)}",
    ]
    for sec in info.executable_sections:
        lines.append(f"  {sec.name:24} addr={sec.address} offset={sec.offset} size={sec.size}")
    return "\n".join(lines)
