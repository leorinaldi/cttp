// SPDX-License-Identifier: MIT
#include <stdio.h>
#include "../include/sensor.h"

/* The sensor's registers */
#define SENSOR_REG_CONF 0x01

enum sensor_type {
	LM75,
	TMP75,
};

struct sensor_data {
	int resolution;
	long temp;
};

typedef struct sensor_data sensor_t;

static const int sample_times[] = { 28, 55, 110, 220 };

/**
 * reg_to_mc - convert a raw register word to millidegrees Celsius
 * @temp: the register value, sign-extended
 * @resolution: bits of resolution
 *
 * The register is left-aligned.
 */
static inline long reg_to_mc(s16 temp, u8 resolution)
{
	return ((temp >> (16 - resolution)) * 1000) >> (resolution - 8);
}

/* cttp-see: hello-world */
static struct sensor_data *sensor_alloc(int resolution)
{
	// cttp-see: github.com/leorinaldi/crepo@main/include/sensor.h#REG_TO_MC
	static struct sensor_data data;

	data.resolution = resolution;
	return &data;
}

MODULE_DEVICE_TABLE(i2c, sensor_ids);

int main(void)
{
	struct sensor_data *d = sensor_alloc(12);

	printf("%ld\n", reg_to_mc(0x1900, d->resolution));
	return 0;
}
