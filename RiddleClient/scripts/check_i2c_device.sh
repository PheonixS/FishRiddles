#!/bin/bash

I2C_ADDRESS="08"
I2C_BUS="1"

if i2cdetect -y $I2C_BUS | grep -q "$I2C_ADDRESS"; then
    exit 0
else
    exit 1
fi
