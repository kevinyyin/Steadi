#include <Wire.h>
#include <math.h>

const uint8_t MPU = 0x68;  // 0x69 if AD0 is wired to 3V3

// ---- Pins ----
const int PIN_RED    = 19;
const int PIN_GREEN  = 18;
const int PIN_BLUE   = 17;   // TX2
const int PIN_BUZZER = 16;   // RX2
const bool COMMON_ANODE = false;  // set true if your RGB LED's long leg goes to 3V3

// ---- Thresholds. Tune these with real tests. ----
const float IMPACT_G   = 2.5;            // total force above this = fall alarm
const float FREEFALL_G = 0.5;            // total force below this = dropping
const float STILL_DPS  = 15.0;           // rotation below this = not moving
const unsigned long ALARM_MS       = 5000;  // how long the alarm lasts after a hit
const unsigned long FLASH_MS       = 150;   // red flash / beep speed
const unsigned long PRINT_EVERY_MS = 250;   // readable line 4x per second

unsigned long alarmUntil = 0;
unsigned long lastPrintMs = 0;
float minG = 99, maxG = 0, maxSpin = 0;  // tracked between printed lines

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setColor(bool r, bool g, bool b) {
  digitalWrite(PIN_RED,   r != COMMON_ANODE);
  digitalWrite(PIN_GREEN, g != COMMON_ANODE);
  digitalWrite(PIN_BLUE,  b != COMMON_ANODE);
}

// Wake the sensor and apply our settings. Returns false if it doesn't answer.
bool initMPU() {
  Wire.beginTransmission(MPU);
  if (Wire.endTransmission() != 0) return false;
  writeReg(0x6B, 0x00);  // wake up (it powers on asleep, reading all zeros)
  delay(100);
  writeReg(0x1A, 0x03);  // low-pass filter ~44 Hz
  writeReg(0x19, 9);     // 100 Hz sample rate
  writeReg(0x1B, 0x08);  // gyro +/-500 deg/s
  writeReg(0x1C, 0x10);  // accel +/-8 g
  return true;
}

// Called when the sensor stops answering or reads all zeros
void recoverMPU(const char* why) {
  Serial.printf("!! Sensor problem (%s) - restarting it...\n", why);
  setColor(false, false, true);   // blue while recovering
  digitalWrite(PIN_BUZZER, LOW);
  Wire.end();
  delay(50);
  Wire.begin(21, 22);
  if (initMPU()) {
    Serial.println("!! Sensor back online.");
  } else {
    Serial.println("!! Sensor not answering - check the VCC/GND/SDA/SCL wires.");
    delay(500);
  }
}

// Which axis is pointing up (the one reading about +1 g when still)
const char* upAxis(float ax, float ay, float az) {
  float x = fabs(ax), y = fabs(ay), z = fabs(az);
  if (x >= y && x >= z) return ax > 0 ? "+X" : "-X";
  if (y >= z)           return ay > 0 ? "+Y" : "-Y";
  return az > 0 ? "+Z" : "-Z";
}

void setup() {
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BLUE, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  setColor(false, false, true);  // blue while starting up

  Serial.begin(115200);
  delay(1500);
  Wire.begin(21, 22);  // SDA, SCL

  // Check the sensor is there
  Wire.beginTransmission(MPU);
  if (Wire.endTransmission() != 0) {
    Serial.println("MPU-6050 NOT FOUND. Check VCC, GND, SDA->21, SCL->22.");
    while (true) {                 // blink red slowly = sensor problem
      setColor(true, false, false); delay(500);
      setColor(false, false, false); delay(500);
    }
  }

  // Read chip ID (0x68 = genuine; other values = clone, still fine)
  Wire.beginTransmission(MPU);
  Wire.write(0x75);
  Wire.endTransmission(false);
  Wire.requestFrom((int)MPU, 1);
  Serial.printf("MPU-6050 found. Chip ID = 0x%02X\n", Wire.read());

  initMPU();

  Serial.println();
  Serial.println("HOW TO READ EACH LINE:");
  Serial.println("  Accel  = force on each axis in g. Sitting still, one axis reads ~1.00 (gravity).");
  Serial.println("  Total  = overall force. ~1.00 g when still, >2.5 g triggers the fall alarm.");
  Serial.println("  Spin   = how fast it's rotating around each axis, in degrees per second.");
  Serial.println("  Tilt   = roll/pitch angle from lying flat, in degrees.");
  Serial.println("  Up     = which side of the sensor is facing up.");
  Serial.println("  State  = STILL / MOVING / FREE-FALL / IMPACT over the last 0.25 s.");
  Serial.println("LED: green = OK, flashing red + beeping = fall detected, blue = restarting sensor.");
  Serial.println();

  setColor(false, true, false);  // green = running and OK
}

void loop() {
  unsigned long now = millis();

  Wire.beginTransmission(MPU);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  if (Wire.requestFrom((int)MPU, 14) != 14) {
    recoverMPU("no response");
    return;
  }

  int16_t raw[7];
  bool allZero = true;
  for (int i = 0; i < 7; i++) {
    raw[i] = (Wire.read() << 8) | Wire.read();
    if (raw[i] != 0) allZero = false;
  }

  // All zeros = the sensor lost power for a moment and restarted asleep.
  // A working sensor never reads exactly 0 on every value.
  if (allZero) {
    recoverMPU("reading all zeros");
    return;
  }

  float ax = raw[0] / 4096.0, ay = raw[1] / 4096.0, az = raw[2] / 4096.0;
  float temp = raw[3] / 340.0 + 36.53;
  float gx = raw[4] / 65.5, gy = raw[5] / 65.5, gz = raw[6] / 65.5;

  float totalG = sqrt(ax * ax + ay * ay + az * az);
  float spin   = sqrt(gx * gx + gy * gy + gz * gz);
  float roll   = atan2(ay, az) * 180.0 / PI;
  float pitch  = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;

  if (totalG < minG) minG = totalG;
  if (totalG > maxG) maxG = totalG;
  if (spin > maxSpin) maxSpin = spin;

  // ---- Fall alarm: any sudden hard force starts (or extends) the alarm ----
  if (totalG > IMPACT_G) {
    if (now >= alarmUntil) {
      Serial.println();
      Serial.printf("*** FALL DETECTED: sudden force of %.1f g ***\n", totalG);
      Serial.println();
    }
    alarmUntil = now + ALARM_MS;
  }

  if (now < alarmUntil) {
    bool on = (now / FLASH_MS) % 2 == 0;   // flash red and beep together
    setColor(on, false, false);
    digitalWrite(PIN_BUZZER, on ? HIGH : LOW);
  } else {
    setColor(false, true, false);          // solid green, buzzer quiet
    digitalWrite(PIN_BUZZER, LOW);
  }

  // ---- Readable serial line ----
  if (now - lastPrintMs >= PRINT_EVERY_MS) {
    lastPrintMs = now;

    const char* state;
    if (minG < FREEFALL_G)       state = "FREE-FALL";
    else if (maxG > IMPACT_G)    state = "IMPACT";
    else if (maxSpin < STILL_DPS && maxG - minG < 0.15) state = "STILL";
    else                         state = "MOVING";

    Serial.printf("Accel X:%+5.2f Y:%+5.2f Z:%+5.2f g | Total:%4.2f g | "
                  "Spin X:%+6.1f Y:%+6.1f Z:%+6.1f deg/s | "
                  "Tilt roll:%+4.0f pitch:%+4.0f | Up:%s | State:%-9s | Alarm:%s | %.1f C\n",
                  ax, ay, az, totalG, gx, gy, gz, roll, pitch,
                  upAxis(ax, ay, az), state, now < alarmUntil ? "ON " : "off", temp);

    minG = 99; maxG = 0; maxSpin = 0;
  }

  delay(10);  // ~100 samples per second
}
