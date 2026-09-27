# Device protocols

Two links, both plain text so you can watch them with `arduino-cli monitor` or `nc`.

## Base station ↔ laptop (USB serial)

115200 baud, 8N1. One command per line, ending in `\n` (a trailing `\r` is ignored).

**Laptop → base station**

| Line | Effect |
|---|---|
| `PING` | Replies `PONG` (the laptop sends this on connect) |
| `CUE start` | Two rising beeps: this is the "Go" cue; timing starts when it's sent |
| `CUE stop` | One long low beep: the step is over |
| `CUE done` | Three-note rising melody: the session is saved |
| `CUE error` | Three quick low beeps: something went wrong (step timed out, sensor dropped out); a cancel plays `stop` |
| `CUE rep` | One short beep: an exercise rep was counted |
| `CUE warn` | Three quick high beeps: swaying in a balance stance or hold; the helper should step closer |
| `CUE alarm` | Four long low beeps: balance lost; the stance stops |
| `LED off` / `LED blue` / `LED green` / `LED amber` / `LED red` | Blue = session in progress; green/amber/red = the fall-risk level of the last check-in |

**Base station → laptop**

| Line | Meaning |
|---|---|
| `READY` | Sent once at boot |
| `PONG` | Reply to `PING` |
| `BTN` | The button was pressed (debounced, sent on press, not release) |
| `ERR <text>` | Unknown command (the laptop logs it) |

**Cue tones** (frequency Hz, duration ms; `0` Hz = silence). The on-screen base station plays the same table.

| Cue | Notes |
|---|---|
| start | 2000/150, 0/80, 3000/150 |
| stop | 1500/600 |
| done | 2093/150, 2637/150, 3136/250 |
| error | 800/100, 0/80, 800/100, 0/80, 800/100 |
| rep | 2500/80 |
| warn | 2500/70, 0/70, 2500/70, 0/70, 2500/70 |
| alarm | 1000/250, 0/100, 1000/250, 0/100, 1000/250, 0/100, 1000/250 |

Cues block the Arduino for their length (at most 1.3 s, the alarm), so a button press shorter than a cue can be missed. Nothing in the check-in asks for a press during a cue. The belt plays cues without blocking.

## Belt → laptop (UDP)

The ESP32 sends a datagram every 50 ms (5 samples at 100 Hz) to the network's broadcast address, or to one IP if `UDP_TARGET_IP` is set in `firmware/esp32_imu/config.h`. Port: `UDP_PORT` (default 4210), matching `checkin serve --udp-port`.

Each datagram holds one line per sample:

```
seq,ms,ax,ay,az,gx,gy,gz
```

| Field | Meaning |
|---|---|
| `seq` | Sample counter from boot; a gap means lost samples |
| `ms` | ESP32 `millis()` when the sample was taken (newest sample ≈ send time, 10 ms apart) |
| `ax ay az` | Acceleration in g, including gravity (±8 g range) |
| `gx gy gz` | Angular rate in °/s (±500 °/s range) |

Axes are the MPU-6050's own. The laptop's scoring doesn't care how the belt is mounted.

The laptop maps `ms` to its own clock using the smallest (arrival time − newest sample time) seen, and starts over if `ms` jumps backwards (the belt rebooted).

Watch it live: `nc -ul 4210` (macOS/Linux).

## Laptop → belt (UDP)

With `--source udp`, the laptop lights the belt's RGB LED: it sends `LED off` / `LED blue` / `LED green` / `LED amber` / `LED red` (same meanings as the base station) back to the address the belt's samples come from, once on every change and again every second, so a lost datagram or a belt reboot still ends up showing the right colour. It also sends each cue once as `CUE <name>` (the names above), and the belt's buzzer plays it; the page stays quiet then (`state.source.beeps`). The belt listens on `UDP_PORT`. Pins: red 19, green 18, blue 17 (override `LED_R_PIN` etc. in `config.h`; `LED_COMMON_ANODE true` for a common-anode LED).
