import React from "react";
import { AbsoluteFill, Easing, Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Check, Picture, Ripples, Rolling, Simulated, trace, Words } from "../Kit";
import { C, INOUT, k, OUT, pulse } from "../theme";

export const GO = 15; // the "Go" beep, on the beat
export const STOP = 150; // sit-down detected
const TUG_S = 10.8; // Simulated: Dad, latest check-in

// Timed Up and Go: the light check-in screen, a timer racing the STEADI 12 s line, the belt spotting the sit-down.
export const Tug: React.FC = () => {
  const frame = useCurrentFrame();
  const t = k(frame, [GO, STOP], [0, TUG_S], Easing.linear);
  const done = k(frame, [STOP, STOP + 8], [0, 1]);
  const walk = k(frame, [GO, STOP], [0, 1], Easing.linear);
  const there = walk < 0.5 ? INOUT(walk * 2) : INOUT((1 - walk) * 2);
  const gaugeW = 680;
  const cut = (12 / 15) * gaugeW;
  const card = k(frame, [0, 20], [0, 100], OUT);
  return (
    <Backdrop color={C.ground} grid="rgba(8,9,18,0.05)">
      <div style={{ position: "absolute", left: 140, top: 200, clipPath: `inset(0 ${100 - card}% 0 0)` }}>
        <Picture src="tug.jpg" w={880} h={660} />
        <svg width={880} height={660} style={{ position: "absolute", left: 0, top: 0 }}>
          <line x1={183} x2={183 + 657 * there} y1={560} y2={560} stroke={C.blue} strokeWidth={6} strokeDasharray="14 10" />
          <circle cx={183 + 657 * there} cy={560} r={14} fill={C.led} stroke="#fff" strokeWidth={4} />
          <text x={840} y={620} textAnchor="end" fill={C.ink} fontSize={30} fontWeight={800}>
            3 m
          </text>
        </svg>
        <Simulated style={{ position: "absolute", right: 20, top: 20, background: "#fff" }} />
      </div>
      <Interactive.Div name="Test name" style={{ position: "absolute", left: 1100, top: 190, color: "#080912" }}>
        <Words text="Check" start={4} style={{ fontSize: 36, fontWeight: 800, color: "#2a4093", letterSpacing: "0.02em" }} />
        <Words text="Timed Up and Go" start={7} stagger={2} style={{ fontSize: 76, fontWeight: 800, fontStretch: "104%", marginTop: 6 }} />
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          left: 1096,
          top: 316,
          fontSize: 250,
          fontWeight: 900,
          color: done > 0 ? C.green : C.ink,
          letterSpacing: "-0.02em",
          display: "flex",
          alignItems: "baseline",
          opacity: k(frame, [8, 14], [0, 1]),
          scale: String(1 + pulse(frame, STOP, 5) * 0.06),
          transformOrigin: "left center",
        }}
      >
        <Rolling value={t} decimals={1} snap />
        <span style={{ fontSize: 90, marginLeft: 16, color: C.muted }}>s</span>
      </div>
      {/* Go cue */}
      <div
        style={{
          position: "absolute",
          left: 170,
          top: 230,
          width: 130,
          height: 130,
          background: C.ink,
          color: "#fff",
          fontSize: 56,
          fontWeight: 900,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: k(frame, [GO - 2, GO], [0, 1]) * k(frame, [GO + 40, GO + 50], [1, 0]),
          scale: String(k(frame, [GO - 2, GO + 8], [0.4, 1], Easing.spring({ damping: 9 }))),
        }}
      >
        Go
      </div>
      <Ripples x={235} y={295} at={[GO]} color={C.ink} max={170} life={22} />
      {/* gauge */}
      <div style={{ position: "absolute", left: 1100, top: 690, width: gaugeW, opacity: k(frame, [10, 18], [0, 1]) }}>
        <div style={{ position: "relative", height: 22, background: C.line }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: (t / 15) * gaugeW, background: done > 0 ? C.green : C.blue }} />
          <div style={{ position: "absolute", left: cut - 2, top: -16, width: 4, height: 54, background: C.red }} />
        </div>
        <div style={{ position: "absolute", left: cut - 200, width: 400, textAlign: "center", top: 46, fontSize: 30, fontWeight: 700, color: C.red }}>
          12 s or more flags
        </div>
      </div>
      {/* trunk pitch trace */}
      <svg width={gaugeW} height={130} style={{ position: "absolute", left: 1100, top: 810, overflow: "visible", opacity: k(frame, [14, 22], [0, 1]) }}>
        <path
          d={trace(0, gaugeW * walk, 160, (u) => {
            const s = u * walk;
            const lean = Math.exp(-((s - 0.04) ** 2) / 0.0008) * 34 + Math.exp(-((s - 0.96) ** 2) / 0.0008) * 34;
            return 70 - lean - 14 * Math.sin(s * 70) * Math.min(1, s * 30) * Math.min(1, (1 - s) * 30);
          })}
          fill="none"
          stroke={C.blue}
          strokeWidth={4}
        />
        <line x1={0} x2={0} y1={0} y2={120} stroke={C.ink} strokeWidth={3} />
        <text x={8} y={128} fill={C.ink} fontSize={26} fontWeight={800}>
          Go
        </text>
        {done > 0 ? (
          <g opacity={done}>
            <line x1={gaugeW} x2={gaugeW} y1={0} y2={120} stroke={C.green} strokeWidth={3} />
            <text x={gaugeW - 8} y={128} textAnchor="end" fill={C.green} fontSize={26} fontWeight={800}>
              sat down, timer stops
            </text>
          </g>
        ) : null}
      </svg>
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <div
          style={{
            position: "absolute",
            left: 1100,
            top: 604,
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontSize: 40,
            fontWeight: 800,
            color: C.green,
            opacity: done,
            translate: `${(1 - done) * 20}px 0`,
          }}
        >
          <Check size={44} color={C.green} progress={k(frame, [STOP + 2, STOP + 12], [0, 1])} />
          Under the 12 s line
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
