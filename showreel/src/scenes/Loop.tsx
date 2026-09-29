import React from "react";
import { AbsoluteFill, Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Led, Ripples, Words } from "../Kit";
import { C, IN, INOUT, k, pulse } from "../theme";

const CX = 960;
const CY = 540;
const R = 280;

const NODES = [
  { name: "Screen", sub: "3 key questions", deg: -90, lit: 30 },
  { name: "Assess", sub: "4 tests, about 3 minutes", deg: 0, lit: 45 },
  { name: "Intervene", sub: "coached exercise", deg: 90, lit: 60 },
  { name: "Track", sub: "trends for the family", deg: 180, lit: 75 },
];

const at = (deg: number, r = R) => [CX + r * Math.cos((deg * Math.PI) / 180), CY + r * Math.sin((deg * Math.PI) / 180)];

// The STEADI loop draws itself, a comet lights each stage on the beat, then the camera dives into "Assess".
export const Loop: React.FC = () => {
  const frame = useCurrentFrame();
  const drawn = k(frame, [0, 30], [0, 1], INOUT);
  const angle = frame < 30 ? -90 + 360 * drawn : 270 + (frame - 30) * 6;
  const circ = 2 * Math.PI * R;
  const zoom = Math.exp(k(frame, [138, 176], [0, Math.log(120)], IN));
  const focus = k(frame, [124, 136], [0, 1]);
  const [ax, ay] = at(0);
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <AbsoluteFill style={{ scale: String(zoom), transformOrigin: `${ax}px ${ay}px` }}>
        <svg width={1920} height={1080} style={{ position: "absolute" }}>
          <circle
            cx={CX}
            cy={CY}
            r={R}
            fill="none"
            stroke="rgba(255,255,255,0.35)"
            strokeWidth={3}
            strokeDasharray={circ}
            strokeDashoffset={circ * (1 - drawn)}
            transform={`rotate(-90 ${CX} ${CY})`}
          />
          <circle cx={CX} cy={CY} r={R - 40} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={2} strokeDasharray="4 12" />
        </svg>
        {Array.from({ length: 16 }, (_, j) => {
          const [x, y] = at(angle - j * (frame < 30 ? 5 : 3.2));
          return (
            <div
              key={j}
              style={{
                position: "absolute",
                left: x - (9 - j * 0.45),
                top: y - (9 - j * 0.45),
                width: 2 * (9 - j * 0.45),
                height: 2 * (9 - j * 0.45),
                borderRadius: "50%",
                background: C.led,
                opacity: (1 - j / 16) * 0.7 * (1 - focus),
              }}
            />
          );
        })}
        {NODES.map((n) => {
          const [x, y] = at(n.deg);
          const lit = k(frame, [n.lit, n.lit + 6], [0, 1]);
          const dim = n.name === "Assess" ? 1 : 1 - focus * 0.75;
          const blue = n.name === "Assess" ? k(frame, [150, 172], [0, 1]) : 0;
          return (
            <React.Fragment key={n.name}>
              <div
                style={{
                  position: "absolute",
                  left: x - 15,
                  top: y - 15,
                  width: 30,
                  height: 30,
                  rotate: "45deg",
                  border: `3px solid ${lit > 0 ? C.led : "rgba(255,255,255,0.5)"}`,
                  background: blue > 0 ? C.blue : lit > 0 ? C.led : C.ink,
                  boxShadow: blue > 0 ? "none" : `0 0 ${30 * lit}px ${C.led}`,
                  scale: String((0.4 + 0.6 * k(frame, [n.lit - 12, n.lit - 4], [0, 1])) * (1 + pulse(frame, n.lit, 5) * 0.6)),
                  opacity: dim,
                }}
              />
              <Ripples x={x} y={y} at={[n.lit]} max={110} life={20} />
              <div
                style={{
                  position: "absolute",
                  opacity: dim * k(frame, [n.lit, n.lit + 8], [0, 1]),
                  translate: `0 ${k(frame, [n.lit, n.lit + 14], [24, 0])}px`,
                  ...(n.deg === -90
                    ? { left: x - 400, width: 800, top: y - 150, textAlign: "center" as const }
                    : n.deg === 90
                      ? { left: x - 400, width: 800, top: y + 40, textAlign: "center" as const }
                      : n.deg === 0
                        ? { left: x + 52, top: y - 56 }
                        : { right: 1920 - x + 52, top: y - 56, textAlign: "right" as const }),
                }}
              >
                <div style={{ fontSize: 64, fontWeight: 800, fontStretch: "110%", color: "#fff", lineHeight: 1.05 }}>{n.name}</div>
                <div style={{ fontSize: 34, fontWeight: 600, color: C.onDarkMuted, marginTop: 6 }}>{n.sub}</div>
              </div>
            </React.Fragment>
          );
        })}
        <Interactive.Div
          name="Center"
          from={82}
          style={{ position: "absolute", left: 660, width: 600, top: 440, textAlign: "center", color: "#ffffff" }}
        >
          <Words text="STEADI" start={0} align="center" style={{ fontSize: 100, fontWeight: 900, fontStretch: "104%", lineHeight: 1 }} />
          <Words text="at home." start={8} align="center" style={{ fontSize: 60, fontWeight: 700, color: "#3aa0ff", marginTop: 8 }} />
        </Interactive.Div>
      </AbsoluteFill>
      {frame < 4 ? <Led x={CX} y={CY} r={15} /> : null}
      <AbsoluteFill style={{ background: C.blue, opacity: k(frame, [170, 178], [0, 1], INOUT) }} />
    </Backdrop>
  );
};
