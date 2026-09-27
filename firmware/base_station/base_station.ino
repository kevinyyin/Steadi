// Base station: start button, RGB LED, passive buzzer.
// Pins: docs/PARTS_LIST.md Section 2. Serial protocol and cue tones: firmware/PROTOCOL.md.

const uint8_t BUTTON_PIN = 2;  // D2 -> button -> GND, internal pull-up
const uint8_t LED_R = 9, LED_G = 6, LED_B = 5;  // each via 470 ohm; not D3/D11 (tone() uses their timer on AVR)
const uint8_t BUZZER_PIN = 8;  // via NPN transistor on an Uno R4; a small piezo can go direct on an Uno R3/Nano
const bool COMMON_ANODE = false;  // true if the LED's longest leg goes to 5V instead of GND
const unsigned long DEBOUNCE_MS = 30;

struct Note {
  uint16_t hz;  // 0 = silence
  uint16_t ms;
};
// Tune these to the buzzer's loudest frequency (usually 2-4 kHz). Keep in sync with PROTOCOL.md.
const Note CUE_START[] = {{2000, 150}, {0, 80}, {3000, 150}};
const Note CUE_STOP[] = {{1500, 600}};
const Note CUE_DONE[] = {{2093, 150}, {2637, 150}, {3136, 250}};
const Note CUE_ERROR[] = {{800, 100}, {0, 80}, {800, 100}, {0, 80}, {800, 100}};
const Note CUE_REP[] = {{2500, 80}};
const Note CUE_WARN[] = {{2500, 70}, {0, 70}, {2500, 70}, {0, 70}, {2500, 70}};
const Note CUE_ALARM[] = {{1000, 250}, {0, 100}, {1000, 250}, {0, 100}, {1000, 250}, {0, 100}, {1000, 250}};

String line;
bool lastPressed = false;
unsigned long lastChange = 0;

// ponytail: blocks up to 600 ms; a press shorter than a cue is missed. Make it non-blocking if that bites.
void play(const Note* notes, size_t n) {
  for (size_t i = 0; i < n; i++) {
    if (notes[i].hz) tone(BUZZER_PIN, notes[i].hz, notes[i].ms);
    delay(notes[i].ms);
  }
  noTone(BUZZER_PIN);
}
#define PLAY(cue) play(cue, sizeof(cue) / sizeof(cue[0]))

void setLed(uint8_t r, uint8_t g, uint8_t b) {
  if (COMMON_ANODE) {
    r = 255 - r;
    g = 255 - g;
    b = 255 - b;
  }
  analogWrite(LED_R, r);
  analogWrite(LED_G, g);
  analogWrite(LED_B, b);
}

void handle(const String& cmd) {
  if (cmd == "PING") Serial.println("PONG");
  else if (cmd == "CUE start") PLAY(CUE_START);
  else if (cmd == "CUE stop") PLAY(CUE_STOP);
  else if (cmd == "CUE done") PLAY(CUE_DONE);
  else if (cmd == "CUE error") PLAY(CUE_ERROR);
  else if (cmd == "CUE rep") PLAY(CUE_REP);
  else if (cmd == "CUE warn") PLAY(CUE_WARN);
  else if (cmd == "CUE alarm") PLAY(CUE_ALARM);
  else if (cmd == "LED off") setLed(0, 0, 0);
  else if (cmd == "LED blue") setLed(0, 0, 255);
  else if (cmd == "LED green") setLed(0, 255, 0);
  else if (cmd == "LED amber") setLed(255, 80, 0);
  else if (cmd == "LED red") setLed(255, 0, 0);
  else {
    Serial.print("ERR unknown command: ");
    Serial.println(cmd);
  }
}

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  setLed(0, 0, 0);
  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      line.trim();
      if (line.length()) handle(line);
      line = "";
    } else if (line.length() < 40) {
      line += c;
    }
  }
  bool pressed = digitalRead(BUTTON_PIN) == LOW;
  if (pressed != lastPressed && millis() - lastChange > DEBOUNCE_MS) {
    lastChange = millis();
    lastPressed = pressed;
    if (pressed) Serial.println("BTN");
  }
}
