// Belt unit: MPU-6050 at +/-8 g, +/-500 deg/s, 100 Hz through the FIFO, sent as UDP text lines.
// Its RGB LED shows what the laptop sends back ("LED green" etc.): blue = check-in running,
// green / amber / red = the fall-risk level of the last check-in. Its buzzer plays the laptop's cues
// ("CUE start" etc.), including "warn" (swaying in a balance stance) and "alarm" (balance lost).
// Wiring: docs/PARTS_LIST.md Section 1. Packet format: firmware/PROTOCOL.md. Settings: config.h.
// Talks to the chip's registers directly, so clone chips with an unexpected WHO_AM_I still work.
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>

#include "config.h"

// RGB LED and buzzer pins (docs/PARTS_LIST.md). Override any of these in config.h.
#ifndef LED_R_PIN
#define LED_R_PIN 19
#endif
#ifndef LED_G_PIN
#define LED_G_PIN 18
#endif
#ifndef LED_B_PIN
#define LED_B_PIN 17
#endif
#ifndef LED_COMMON_ANODE
#define LED_COMMON_ANODE false  // true if the LED's long leg goes to 3V3
#endif
#ifndef BUZZER_PIN
#define BUZZER_PIN 16
#endif
#ifndef BUZZER_ACTIVE
#define BUZZER_ACTIVE true  // true: beeps by itself when powered (one pitch); false: passive, driven with tone()
#endif

enum : uint8_t {
  SMPLRT_DIV = 0x19,
  CONFIG = 0x1A,
  GYRO_CONFIG = 0x1B,
  ACCEL_CONFIG = 0x1C,
  FIFO_EN = 0x23,
  INT_STATUS = 0x3A,
  USER_CTRL = 0x6A,
  PWR_MGMT_1 = 0x6B,
  FIFO_COUNTH = 0x72,
  FIFO_R_W = 0x74,
  WHO_AM_I = 0x75,
};
const float ACC_LSB_PER_G = 4096.0;   // +/-8 g
const float GYRO_LSB_PER_DPS = 65.5;  // +/-500 deg/s
const int SAMPLE_BYTES = 12;          // accel x, y, z then gyro x, y, z; big-endian int16
const uint32_t SAMPLE_MS = 10;        // 100 Hz

WiFiUDP udp;
IPAddress unicastIp;
bool unicast = false;
bool mpuReady = false;
bool listening = false;  // udp is bound to UDP_PORT, so the laptop's LED and CUE messages reach it
uint32_t seq = 0;

// Cue tones from firmware/PROTOCOL.md: {Hz, ms}, 0 Hz = silence. An active buzzer ignores the pitch.
struct Note {
  uint16_t hz, ms;
};
const Note CUE_START[] = {{2000, 150}, {0, 80}, {3000, 150}};
const Note CUE_STOP[] = {{1500, 600}};
const Note CUE_DONE[] = {{2093, 150}, {2637, 150}, {3136, 250}};
const Note CUE_ERROR[] = {{800, 100}, {0, 80}, {800, 100}, {0, 80}, {800, 100}};
const Note CUE_REP[] = {{2500, 80}};
const Note CUE_WARN[] = {{2500, 70}, {0, 70}, {2500, 70}, {0, 70}, {2500, 70}};
const Note CUE_ALARM[] = {{1000, 250}, {0, 100}, {1000, 250}, {0, 100}, {1000, 250}, {0, 100}, {1000, 250}};
const Note* playing = nullptr;  // the cue being played, advanced by pollBuzzer() so the loop never waits
size_t playLen = 0, playIdx = 0;
uint32_t noteEnd = 0;

void buzz(uint16_t hz) {
  if (BUZZER_ACTIVE) digitalWrite(BUZZER_PIN, hz ? HIGH : LOW);
  else if (hz) tone(BUZZER_PIN, hz);
  else noTone(BUZZER_PIN);
}

void startCue(const Note* notes, size_t n) {
  playing = notes;
  playLen = n;
  playIdx = 0;
  buzz(notes[0].hz);
  noteEnd = millis() + notes[0].ms;
}
#define CUE(c) startCue(c, sizeof(c) / sizeof(c[0]))

void playCue(const char* name) {
  if (!strncmp(name, "start", 5)) CUE(CUE_START);
  else if (!strncmp(name, "stop", 4)) CUE(CUE_STOP);
  else if (!strncmp(name, "done", 4)) CUE(CUE_DONE);
  else if (!strncmp(name, "error", 5)) CUE(CUE_ERROR);
  else if (!strncmp(name, "rep", 3)) CUE(CUE_REP);
  else if (!strncmp(name, "warn", 4)) CUE(CUE_WARN);
  else if (!strncmp(name, "alarm", 5)) CUE(CUE_ALARM);
}

void pollBuzzer() {
  if (!playing || (int32_t)(millis() - noteEnd) < 0) return;
  if (++playIdx >= playLen) {
    buzz(0);
    playing = nullptr;
    return;
  }
  buzz(playing[playIdx].hz);
  noteEnd = millis() + playing[playIdx].ms;
}

void writeLed(uint8_t r, uint8_t g, uint8_t b) {
  if (LED_COMMON_ANODE) {
    r = 255 - r;
    g = 255 - g;
    b = 255 - b;
  }
  analogWrite(LED_R_PIN, r);
  analogWrite(LED_G_PIN, g);
  analogWrite(LED_B_PIN, b);
}

void setLed(const char* color) {
  if (!strncmp(color, "green", 5)) writeLed(0, 255, 0);
  else if (!strncmp(color, "amber", 5)) writeLed(255, 70, 0);  // tune the green part if it looks too yellow
  else if (!strncmp(color, "red", 3)) writeLed(255, 0, 0);
  else if (!strncmp(color, "blue", 4)) writeLed(0, 0, 255);
  else writeLed(0, 0, 0);  // "off" or anything unknown
}

// Apply any "LED <color>" / "CUE <name>" lines the laptop sent (firmware/PROTOCOL.md). Never blocks.
void pollLaptop() {
  if (!listening) {
    if (WiFi.status() != WL_CONNECTED) return;
    listening = udp.begin(UDP_PORT);
  }
  while (udp.parsePacket()) {
    char buf[32];
    int n = udp.read(buf, sizeof(buf) - 1);
    buf[n > 0 ? n : 0] = 0;
    if (!strncmp(buf, "LED ", 4)) setLed(buf + 4);
    else if (!strncmp(buf, "CUE ", 4)) playCue(buf + 4);
  }
}

bool writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool readRegs(uint8_t reg, uint8_t* buf, size_t n) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint16_t)MPU_ADDR, n) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

void resetFifo() {
  writeReg(USER_CTRL, 0x04);  // FIFO_RESET
  writeReg(USER_CTRL, 0x40);  // FIFO_EN
}

bool setupMpu() {
  uint8_t who = 0;
  if (!readRegs(WHO_AM_I, &who, 1)) {
    Serial.printf("No MPU-6050 at 0x%02X: check wiring and I2C_SDA=%d, I2C_SCL=%d in config.h\n", MPU_ADDR, I2C_SDA,
                  I2C_SCL);
    return false;
  }
  if (who != 0x68) Serial.printf("WHO_AM_I is 0x%02X, not 0x68 (probably a clone); continuing\n", who);
  writeReg(PWR_MGMT_1, 0x80);  // reset the chip
  delay(100);
  bool ok = writeReg(PWR_MGMT_1, 0x01)   // wake up, clock from the X gyro
            && writeReg(CONFIG, 0x03)       // built-in low-pass filter at 44 Hz (gyro output 1 kHz)
            && writeReg(SMPLRT_DIV, 9)      // 1 kHz / (1 + 9) = 100 Hz
            && writeReg(GYRO_CONFIG, 0x08)  // +/-500 deg/s
            && writeReg(ACCEL_CONFIG, 0x10) // +/-8 g
            && writeReg(FIFO_EN, 0x78);     // accel and gyro x, y, z into the FIFO
  resetFifo();
  Serial.println(ok ? "MPU-6050 streaming at 100 Hz" : "MPU-6050 setup failed; retrying");
  return ok;
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // power saving delays and drops packets
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Joining Wi-Fi \"%s\"", WIFI_SSID);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("IP %s, sending to %s:%d\n", WiFi.localIP().toString().c_str(),
                  unicast ? UDP_TARGET_IP : "broadcast", UDP_PORT);
  } else {
    Serial.println("Wi-Fi not connected yet; will keep trying in the background");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  pinMode(LED_R_PIN, OUTPUT);
  pinMode(LED_G_PIN, OUTPUT);
  pinMode(LED_B_PIN, OUTPUT);
  setLed("off");
  unicast = strlen(UDP_TARGET_IP) > 0 && unicastIp.fromString(UDP_TARGET_IP);
  Wire.begin(I2C_SDA, I2C_SCL, 400000);
  connectWifi();
  mpuReady = setupMpu();
}

void loop() {
  pollLaptop();
  pollBuzzer();
  if (!mpuReady) {
    delay(1000);
    mpuReady = setupMpu();
    return;
  }
  uint8_t status = 0, cnt[2];
  if (readRegs(INT_STATUS, &status, 1) && (status & 0x10)) {
    Serial.println("FIFO overflowed; resetting");
    resetFifo();
    return;
  }
  if (!readRegs(FIFO_COUNTH, cnt, 2)) {
    Serial.println("Lost the MPU-6050 on I2C");
    mpuReady = false;
    return;
  }
  uint16_t count = (cnt[0] << 8) | cnt[1];
  if (count % SAMPLE_BYTES) {  // out of step with sample boundaries: start clean
    resetFifo();
    return;
  }
  int n = count / SAMPLE_BYTES;
  if (n < BATCH_SAMPLES) {
    delay(2);
    return;
  }
  uint32_t now = millis();  // the newest sample in the FIFO was taken within the last 10 ms
  bool send = WiFi.status() == WL_CONNECTED;  // keep draining the FIFO even when Wi-Fi is down
  if (send) udp.beginPacket(unicast ? unicastIp : WiFi.broadcastIP(), UDP_PORT);
  for (int i = 0; i < n; i++) {
    uint8_t b[SAMPLE_BYTES];
    if (!readRegs(FIFO_R_W, b, SAMPLE_BYTES)) {
      mpuReady = false;
      break;
    }
    int16_t v[6];
    for (int k = 0; k < 6; k++) v[k] = (int16_t)((b[2 * k] << 8) | b[2 * k + 1]);
    uint32_t t = now - (uint32_t)(n - 1 - i) * SAMPLE_MS;
    if (send) {
      udp.printf("%lu,%lu,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f\n", (unsigned long)seq, (unsigned long)t,
                 v[0] / ACC_LSB_PER_G, v[1] / ACC_LSB_PER_G, v[2] / ACC_LSB_PER_G, v[3] / GYRO_LSB_PER_DPS,
                 v[4] / GYRO_LSB_PER_DPS, v[5] / GYRO_LSB_PER_DPS);
    }
    seq++;
  }
  if (send) udp.endPacket();
}
