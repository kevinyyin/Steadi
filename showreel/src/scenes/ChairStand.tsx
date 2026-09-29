import React from "react";
import { AbsoluteFill, Interactive, useCurrentFrame } from "remotion";
import { noise2D } from "@remotion/noise";
import { Backdrop, Check, Rolling, Simulated, trace, Words } from "../Kit";
import { C, k, pulse } from "../theme";

// A stand every dotted eighth (11.25 frames): the rep beeps ride against the beat. 12 stands, Simulated.
export const REPS = Array.from({ length: 12 }, (_, i) => Math.round(8 + i * 11.25));
const T0 = 8;
const T1 = 140;
const CX = 600;
const CY = 560;
const R = 260;

const bump = (d: number) => Math.exp(-((d - 3) ** 2) / 6) - 0.45 * Math.exp(-((d - 8) ** 2) / 5);

// 30-second chair stand: a draining ring, a rolling count, a velocity trace that spikes on every rise.
export const ChairStand: React.FC = () => {
  const frame = useCurrentFrame();
  const count = REPS.reduce((n, r) => n + k(frame, [r, r + 5], [0, 1]), 0);
  const slam = REPS.reduce((m, r) => Math.max(m, pulse(frame, r, 4)), 0);
  const left = k(frame, [T0, T1], [1, 0], (t) => t);
  const circ = 2 * Math.PI * R;
  const result = k(frame, [T1 + 4, T1 + 14], [0, 1]);
  const traceW = 780;
  const sig = (tf: number) => (tf < 0 ? 0 : REPS.reduce((s, r) => s + bump(tf - r), 0) + 0.06 * noise2D("vel", tf * 0.3, 0));
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <svg width={1920} height={1080} style={{ position: "absolute" }}>
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={26} />
        <circle
          cx={CX}
          cy={CY}
          r={R}
          fill="none"
          stroke={C.led}
          strokeWidth={26}
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - left) * -1}
          transform={`rotate(-90 ${CX} ${CY})`}
          style={{ filter: `drop-shadow(0 0 12px ${C.led})` }}
          opacity={k(frame, [0, 8], [0, 1])}
        />
        {REPS.filter((r) => frame >= r).map((r) => {
          const a = (-90 + 360 * ((r - T0) / (T1 - T0))) * (Math.PI / 180);
          const grow = k(frame, [r, r + 6], [0, 1]);
          return (
            <line
              key={r}
              x1={CX + (R + 22) * Math.cos(a)}
              y1={CY + (R + 22) * Math.sin(a)}
              x2={CX + (R + 22 + 26 * grow) * Math.cos(a)}
              y2={CY + (R + 22 + 26 * grow) * Math.sin(a)}
              stroke="#fff"
              strokeWidth={5}
            />
          );
        })}
      </svg>
      <div
        style={{
          position: "absolute",
          left: CX - 250,
          width: 500,
          top: CY - 180,
          display: "flex",
          justifyContent: "center",
          fontSize: 290,
          fontWeight: 900,
          color: "#fff",
          lineHeight: 1,
          scale: String(1 + slam * 0.1),
        }}
      >
        <Rolling value={count} digits={1} />
      </div>
      <div style={{ position: "absolute", left: CX - 200, width: 400, top: CY + 130, textAlign: "center", fontSize: 40, fontWeight: 700, color: C.onDarkMuted }}>
        {Math.ceil(left * 30)} s left
      </div>
      <Interactive.Div name="Chair stand title" style={{ position: "absolute", left: 1000, top: 170, color: "#ffffff" }}>
        <Words text="Check" start={2} style={{ fontSize: 36, fontWeight: 800, color: "#3aa0ff" }} />
        <Words text={"30-second\nchair stand."} start={4} stagger={3} style={{ fontSize: 110, fontWeight: 900, fontStretch: "108%", lineHeight: 1, marginTop: 8 }} />
      </Interactive.Div>
      <Simulated dark style={{ position: "absolute", left: 140, top: 150 }} />
      <svg width={traceW} height={170} style={{ position: "absolute", left: 1000, top: 500, overflow: "visible" }}>
        <line x1={0} x2={traceW} y1={120} y2={120} stroke="rgba(255,255,255,0.2)" strokeWidth={2} />
        <path d={trace(0, traceW, 200, (u) => 120 - 95 * sig(frame - 75 + u * 75))} fill="none" stroke={C.led} strokeWidth={4} />
        <text x={0} y={200} fill={C.onDarkMuted} fontSize={26} fontWeight={700}>
          upward speed at the lower back: one peak per stand
        </text>
      </svg>
      <AbsoluteFill>
        <div style={{ position: "absolute", left: 1000, top: 740, fontSize: 36, fontWeight: 600, color: C.onDarkMuted, lineHeight: 1.35, opacity: k(frame, [30, 40], [0, 1]) }}>
          Men 75–79: fewer than 11 flags.
          <br />
          Arms used? It records 0, as STEADI says.
        </div>
        <div
          style={{
            position: "absolute",
            left: 1000,
            top: 872,
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "14px 24px 14px 16px",
            background: C.green,
            color: "#fff",
            fontSize: 40,
            fontWeight: 800,
            opacity: result,
            translate: `${(1 - result) * 30}px 0`,
          }}
        >
          <Check size={44} progress={k(frame, [T1 + 8, T1 + 18], [0, 1])} />
          12 stands: not below average for age
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
