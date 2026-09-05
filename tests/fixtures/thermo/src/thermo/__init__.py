"""thermo: read temperatures from I2C sensors."""

from .decode import reg_to_millicelsius
from .lm75 import LM75

__all__ = ["LM75", "reg_to_millicelsius"]
