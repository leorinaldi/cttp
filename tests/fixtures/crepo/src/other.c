// SPDX-License-Identifier: MIT
#include "../include/sensor.h"

/* The same decoder with other names and other constants: one shape, another identity. */
static inline long raw_to_millic(s16 raw, u8 bits)
{
	/* half-degree steps */
	return ((raw >> (12 - bits)) * 500) >> (bits - 4);
}

/* The statements in another order: a different shape. */
static inline long reordered(s16 raw, u8 bits)
{
	return (raw >> (bits - 4)) * ((500 >> (12 - bits)));
}
