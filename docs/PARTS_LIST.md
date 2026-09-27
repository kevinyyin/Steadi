# Final Build Parts List

Fall-prevention belt: screen → assess → intervene → track. Sources: **Team** = hackathon BOM (`BOM.md`), **Hive** = makerspace (one trip; solder there), **Personal** = our own devices, **Venue** = hackathon space.

---

## 1. Belt Unit (worn at the lower back)

| Part | Qty | Source | Notes |
|---|---|---|---|
| ESP32 dev board | 1 (+1 spare) | Hive (checkout) | Reads the sensor, streams over Wi-Fi |
| MPU-6050 (GY-521 breakout) | 1 (+1 spare) | Hive (checkout) | 6-axis IMU; solder headers on at Hive |
| Male pin header strip (1 row) | 1 | Hive (Bench 8) | For the MPU-6050s |
| Female-to-female jumper wires | 4 (+spares) | Hive / Team | ESP32 ↔ MPU-6050; no breadboard on the belt |
| USB power bank | 1 | Team "Battery Pack" or Personal | Powers the ESP32 through its USB port (see Section 6) |
| USB cable for the ESP32 | 1 | Team | Micro-USB or USB-C, whichever the ESP32 has; short is better |
| Elastic band + velcro, or a fanny pack | 1 belt | Hive / Personal | Holds everything firmly at the lower back |
| Electrical tape or hot glue | a little | Hive / Team | Stops jumpers pulling loose while walking |

**Wiring**
| MPU-6050 | ESP32 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 21 (classic ESP32) |
| SCL | GPIO 22 (classic ESP32) |
| AD0 | GND (address 0x68) or leave unconnected |
| XDA, XCL, INT | Unconnected |

![MPU-6050 wiring on a classic ESP32](diagrams/belt-mpu6050.svg)

The belt status LED and buzzer are not in the table above. The ESP32 sketch uses these pins:

![Belt status LED and buzzer pins](diagrams/belt-status.svg)

GPIO 21/22 are the default I2C pins on a classic ESP32 dev board. ESP32-S2/S3/C3 boards use different defaults; if yours is one, wire to any two free pins and set them in code with `Wire.begin(SDA, SCL)`. The chip name is printed on the ESP32's metal shield.

**MPU-6050 settings:** accelerometer ±8 g, gyroscope ±500 °/s, 100 Hz, built-in low-pass filter on, read from the FIFO buffer.

**Network:** the ESP32 broadcasts UDP on the local network, so it works without knowing the laptop's IP. Some hotspots drop broadcast packets, so the firmware also supports sending to one IP (unicast) as a setting. Wi-Fi name/password and UDP port are settings, not hard-coded.

---

## 2. Base Station (on the table)

| Part | Qty | Source | Notes |
|---|---|---|---|
| Arduino (Uno R4 preferred, or a Nano with soldered headers) | 1 | Team | Plus a matching USB cable to the laptop |
| Breadboard | 1 | Team | |
| Push button | 1 (+1 spare) | Hive (Bench 8) | Start button |
| RGB LED | 1 | Team (on hand) | Green / amber / red result |
| 470 Ω resistors | 3 | Team | One per LED color (safe for the Uno R4's 8 mA pin limit) |
| Passive buzzer | 1 | Team (on hand) | Driven with `tone()` |
| NPN transistor + 1 kΩ resistor | 1 each | Team (transistor packs) | Drives the buzzer on an Uno R4 (see note) |
| Male-to-male jumper wires | ~8 | Team | |

**Wiring**
| Part | Arduino pin | Notes |
|---|---|---|
| Button | D2 → button → GND | `INPUT_PULLUP`, no resistor needed |
| RGB red | D9 | via 470 Ω |
| RGB green | D6 | via 470 Ω |
| RGB blue | D5 | via 470 Ω |
| RGB common leg | GND (common-cathode) or 5V (common-anode, inverted code) | Longest leg |
| Buzzer | D8 → 1 kΩ → transistor base; buzzer between 5V and collector; emitter → GND | On a classic Nano/Uno R3, a small piezo buzzer can go D8 → buzzer → GND directly |

![Base station button and RGB LED](diagrams/base-button-led.svg)

![Base-station buzzer on an Uno R4](diagrams/base-buzzer-r4.svg)

![Base-station buzzer on a classic Nano or Uno R3](diagrams/base-buzzer-classic.svg)

**Pin current:** the Uno R4's pins supply at most **8 mA** each (classic Nano/Uno R3: about 20 mA). 470 Ω keeps each LED color under that; a buzzer can draw more, so on the R4 it goes through the transistor. On classic boards, `tone()` disables PWM on D3/D11, which is why the LED uses D5/D6/D9.

**Buzzer cues:** start = two rising beeps (2000 → 3000 Hz); stop = one long low beep (1500 Hz, 600 ms); done = three-note rising melody; error = three quick low beeps. Tune to the buzzer's loudest frequency (usually 2–4 kHz).

---

## 3. Brains, Network, Display

| Part | Source | Role |
|---|---|---|
| My laptop + charger | Personal | The only dev and demo machine: Claude Code, firmware uploads, session controller, dashboard |
| Phone hotspot (preferred) or Access Point | Personal / Team | One network for laptop, ESP32, tablet, phones. Not venue Wi-Fi. |
| Dell Venue 10 Pro tablet | Team | The "family" dashboard screen |

---

## 4. Test Station

| Part | Source | Used for |
|---|---|---|
| Standard arm chair | Venue | Timed Up and Go (STEADI setup) |
| Straight-back chair, no arms, ~17-inch seat | Venue | 30-second chair stand and sit-to-stand exercises (STEADI setup); if only one chair, use this for both |
| Masking tape + tape measure | Hive | A 3 m (10 ft) line for Timed Up and Go |
| Counter or wall | Venue | Supported balance stances and balance exercises |

---

## 5. Backups & Upgrades

| Part | Source | When |
|---|---|---|
| Phone in a belt pouch running phyphox | Pixel / teammate's phone | Backup motion sensor if the ESP32 belt fails |
| Second phone + wired earbuds with inline mic | Pixel / Personal | Audio upgrade: talk detection, animal counting |
| Keyboard | Team | Fallback: teammate taps a key per animal |
| Ultrasonic distance sensor | Hive (no checkout) | Optional automatic walk timer to double-check walking speed |
| 4× AAA battery holder + AAA batteries | Hive (holder) + buy batteries | Backup ESP32 power if no power bank (see Section 6) |

---

## 6. Powering the ESP32

![How the ESP32 belt is powered](diagrams/belt-power.svg)

**Primary: USB power bank → ESP32's USB port.** The board's built-in regulator turns the 5 V into the 3.3 V the ESP32 needs, and the MPU-6050 runs off the ESP32's 3V3 pin (a few mA). Simplest and most reliable.
- **Current:** roughly 100–150 mA on average with Wi-Fi on, with short spikes of a few hundred mA when transmitting. Any normal power bank handles this for many hours.
- **Auto-shutoff:** this draw is usually high enough to keep a power bank awake, but test for 20+ minutes before relying on it.

**Backup: 4× AAA holder → ESP32's VIN (or 5V) pin + GND.** Four fresh AA/AAA alkalines give ~6 V, which the regulator handles.
- **Don't use 3× AAA** (~4.5 V, sagging lower as they drain): too little headroom for the regulator, causing random resets when Wi-Fi transmits.
- Solder the holder's leads to header pins at Hive (no wire strippers at the hackathon).

**Never:**
- Connect batteries directly to the **3V3 pin**. It bypasses the regulator; anything above ~3.6 V can damage the ESP32.
- Power from USB and VIN at the same time.

**Symptom of weak power:** the serial monitor shows "Brownout detector was triggered" and the board restarts, usually when Wi-Fi connects. Fix: power bank, shorter/better USB cable.

---

## 7. Hive Trip Checklist (one trip)
**Before going:** run the setup prompt (Step 0 in `KICKOFF_PROMPT.md`): uv, arduino-cli, ESP32 core, both MPU-6050 libraries. Bring the laptop and charger. If the ESP32 doesn't show up as a port when plugged in, install its USB driver (CP210x or CH340).

**At Hive:**
1. Collect the parts marked Hive above.
2. Solder headers onto both MPU-6050s (and the ESP32 if it has none).
3. Wire ESP32 + MPU-6050; upload an I2C scanner with arduino-cli and watch `arduino-cli monitor` (expect 0x68); confirm live readings change when moved. If the Adafruit library refuses to start, it's likely a clone chip; use the Electronic Cats library.
4. Test the spare MPU-6050.
5. If using the AAA backup, solder the holder leads to header pins.
6. Ask the front desk: does checkout cover the whole hackathon? Can we return the MPU-6050s with headers soldered on? (If not: solder wick is out of stock; manual solder suckers are available.)

---

## 8. Not in the Build
LilyPad, haptic motor breakout, vibration motor, WYZE cam, IMU breakout (out of stock; MPU-6050 covers it), microphone breakout, stepper motor, relays, RFID/NFC.

## 9. Still to Confirm
- A USB power bank.
- Which Arduino (and matching cable) the team has for the base station.
- ESP32's USB connector type (micro-USB vs. USB-C) vs. our cables.
- The laptop, ESP32, and tablet can all join a phone hotspot and reach each other.
