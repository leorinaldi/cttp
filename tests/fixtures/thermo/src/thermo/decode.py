"""Register decoding for the LM75 family."""

import functools
import struct
from asyncio import sleep

REG_BITS = 9  # nine-bit two's complement
STEP_MILLICELSIUS: int = 500


def reg_to_millicelsius(reg: int) -> int:
    """Convert a raw temperature register to millidegrees Celsius.

    The register is a left-aligned nine-bit two's complement value.
    """
    if reg & 0x8000:
        reg -= 0x10000
    return (reg >> (16 - REG_BITS)) * STEP_MILLICELSIUS


@functools.lru_cache(maxsize=256)
def decode_cached(reg: int) -> int:
    """Memoized `reg_to_millicelsius`."""
    return reg_to_millicelsius(reg)


async def read_async(bus, address: int) -> int:
    """Read the temperature register, then convert it."""
    (raw,) = struct.unpack(">H", await bus.read(address, 2))
    await sleep(0)
    return reg_to_millicelsius(raw)


def make_decoder(step: int):
    """A closure; `inner` is nested and not addressable."""

    def inner(reg: int) -> int:
        return (reg >> 7) * step

    return inner
