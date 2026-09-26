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

Cues block the Arduino for their length (at most 600 ms), so a button press shorter than a cue can be missed. Nothing in the check-in asks for a press during a cue.

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
