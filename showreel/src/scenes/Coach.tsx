import React from "react";
import { Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Check, Picture, Rolling, Simulated, Words } from "../Kit";
import { C, INOUT, k, OUT, pulse } from "../theme";

export const COACH_REPS = Array.from({ length: 8 }, (_, i) => 15 + i * 15);
export const DAY_TICKS = [128, 135, 143, 150, 158];
const DAYS = ["M", "T", "W", "T", "F", "S", "S"];
const DONE_DAYS = [0, 1, 2, 4, 5];
const PX = 1060;
const PW = 720;

// Exercise mode: every rep fills a segment with a beep, then the week's exercise days check off.
export const Coach: React.FC = () => {
  const frame = useCurrentFrame();
  const count = COACH_REPS.reduce((n, r) => n + k(frame, [r, r + 5], [0, 1]), 0);
  const bounce = COACH_REPS.reduce((m, r) => Math.max(m, pulse(frame, r, 5)), 0);
  const wipe = k(frame, [118, 132], [0, 100], INOUT);
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <Interactive.Div name="Coach title" style={{ position: "absolute", left: 140, top: 180, color: "#ffffff" }}>
        <Words text="Coach" start={0} style={{ fontSize: 40, fontWeight: 800, color: "#3aa0ff" }} />
        <Words text={"Every rep\ncounted."} start={3} stagger={3} style={{ fontSize: 150, fontWeight: 900, fontStretch: "110%", lineHeight: 1, marginTop: 10 }} />
        <Words
          text={"Sit-to-stands and supported\nbalance holds, so the family\nknows they happened."}
          start={12}
          stagger={1}
          style={{ fontSize: 48, fontWeight: 600, color: "#b9bdcc", marginTop: 40, lineHeight: 1.2 }}
        />
      </Interactive.Div>
      <div style={{ position: "absolute", left: PX, top: 180, width: PW, clipPath: `inset(${wipe}% 0 0 0)` }}>
        <div style={{ scale: String(1 + bounce * 0.025), opacity: k(frame, [0, 12], [0, 1]), translate: `0 ${k(frame, [0, 16], [50, 0], OUT)}px` }}>
          <Picture src="sit_to_stand.jpg" w={PW} h={520} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 26, color: "#fff" }}>
          <div style={{ fontSize: 36, fontWeight: 800 }}>Sit-to-stand, set 1</div>
          <div style={{ fontSize: 60, fontWeight: 900, display: "flex", alignItems: "baseline" }}>
            <Rolling value={count} digits={1} />
            <span style={{ color: C.onDarkMuted, fontSize: 44, marginLeft: 10 }}>/ 8</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 14 }}>
          {COACH_REPS.map((r, i) => {
            const on = k(frame, [r, r + 4], [0, 1]);
            return (
              <div
                key={i}
                style={{
                  flex: 1,
                  height: 34,
                  background: on > 0 ? C.led : "rgba(255,255,255,0.12)",
                  boxShadow: `0 0 ${24 * pulse(frame, r, 6)}px ${C.led}`,
                  scale: `1 ${1 + pulse(frame, r, 4) * 0.5}`,
                }}
              />
            );
          })}
        </div>
      </div>
      {frame >= 120 ? (
        <div style={{ position: "absolute", left: PX, top: 260, width: PW, color: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Words text="This week" start={122} style={{ fontSize: 40, fontWeight: 800, color: C.blueSoft }} />
            <Simulated dark />
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 30 }}>
            {DAYS.map((d, i) => {
              const tick = DONE_DAYS.indexOf(i);
              const at = tick >= 0 ? DAY_TICKS[tick] : 999;
              const on = k(frame, [at, at + 5], [0, 1]);
              return (
                <div key={i} style={{ flex: 1, textAlign: "center", opacity: k(frame, [120 + i * 1.5, 128 + i * 1.5], [0, 1]) }}>
                  <div style={{ fontSize: 30, fontWeight: 700, color: C.onDarkMuted, marginBottom: 12 }}>{d}</div>
                  <div
                    style={{
                      height: 92,
                      border: `3px solid ${on > 0 ? C.greenLit : "rgba(255,255,255,0.25)"}`,
                      background: on > 0 ? C.green : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      scale: String(1 + pulse(frame, at, 5) * 0.12),
                    }}
                  >
                    {on > 0 ? <Check size={50} progress={on} /> : null}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 60, fontWeight: 900, marginTop: 50, opacity: k(frame, [158, 166], [0, 1]), lineHeight: 1.05 }}>
            5 exercise days.
            <br />
            Target met.
          </div>
          <div style={{ fontSize: 34, fontWeight: 600, color: C.onDarkMuted, marginTop: 16, lineHeight: 1.3, opacity: k(frame, [162, 170], [0, 1]) }}>
            Reps step up after enough exercise days.
          </div>
        </div>
      ) : null}
    </Backdrop>
  );
};
