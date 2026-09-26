#pragma once
// Belt settings. Wi-Fi name and password go in secrets.h (git-ignored): copy secrets.example.h.
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"  // placeholders: builds, but won't join Wi-Fi
#endif

#define UDP_PORT 4210    // must match `checkin serve --udp-port` (default 4210)
#define UDP_TARGET_IP "" // "" = broadcast to the network; set the laptop's IP if the hotspot drops broadcasts
#define I2C_SDA 21       // classic ESP32 defaults; ESP32-S2/S3/C3: wire any two free pins and set them here
#define I2C_SCL 22
#define MPU_ADDR 0x68    // AD0 to GND or unconnected; 0x69 if AD0 is tied high
#define BATCH_SAMPLES 5  // samples per UDP packet: 5 at 100 Hz = one packet every 50 ms
