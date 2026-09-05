/* SPDX-License-Identifier: MIT */
#ifndef SENSOR_H
#define SENSOR_H

#define SENSOR_REG_TEMP 0x00
#define REG_TO_MC(reg) (((reg) >> 7) * 500)

typedef short s16;
typedef unsigned char u8;

long reg_to_mc(s16 temp, u8 resolution);

#endif
