// SPDX-License-Identifier: MIT
#include "../include/sensor.h"

/* A second driver for the same silicon: the decoder copied verbatim. */
static inline long reg_to_mc(s16 temp, u8 resolution)
{
	return ((temp >> (16 - resolution)) * 1000) >> (resolution - 8);
}

long twin_read(s16 raw)
{
	return reg_to_mc(raw, 12);
}
