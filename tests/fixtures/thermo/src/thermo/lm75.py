"""The LM75 temperature sensor."""

import smbus2

from . import decode
from .decode import reg_to_millicelsius

DEFAULT_ADDRESS = 0x48


class LM75:
    """An LM75 on an I2C bus.

    Reads the temperature register and decodes it.
    """

    ADDRESS = DEFAULT_ADDRESS
    RESOLUTION: float = 0.5

    def __init__(self, bus: smbus2.SMBus, address: int = ADDRESS):
        self.bus = bus
        self.address = address

    def read_temp(self) -> float:
        """The temperature in degrees Celsius."""
        raw = self.bus.read_word_data(self.address, 0)
        return reg_to_millicelsius(raw) / 1000

    @staticmethod
    def step() -> int:
        return decode.STEP_MILLICELSIUS
