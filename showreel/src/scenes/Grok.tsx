import React from "react";
import { Easing, Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Check, Words } from "../Kit";
import { C, k, OUT, pulse } from "../theme";

const SUMMARY =
  "Dad's chair stands dipped in weeks 4 and 5, then came back up to 13. He has exercised 5 days a week since the plan started.";
export const GUARDS: [string, number][] = [
  ["Every number is in the data", 60],
  ["No diagnosis or prediction", 70],
  ["No clinical jargon", 80],
  ["Grok off? Fixed wording, offline", 90],
];
export const TYPE: [number, number] = [14, 78];

// The family summary types itself out while the guardrails tick through their checks.
export const Grok: React.FC = () => {
  const frame = useCurrentFrame();
  const n = Math.floor(k(frame, TYPE, [0, SUMMARY.length], Easing.linear));
  const typing = frame < TYPE[1] + 4;
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <Interactive.Div name="Grok title" style={{ position: "absolute", left: 140, top: 120, fontSize: 100, fontWeight: 900, fontStretch: "106%", lineHeight: 1.04 }}>
        <Words text="Grok writes it." start={0} stagger={3} style={{ color: "#ffffff" }} />
        <Words text="Guardrails check it." start={6} stagger={3} style={{ color: "#3aa0ff" }} />
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 420,
          width: 940,
          minHeight: 400,
          background: C.paper,
          padding: "32px 36px",
          color: C.ink,
          opacity: k(frame, [4, 12], [0, 1]),
          translate: `0 ${k(frame, [4, 20], [60, 0], OUT)}px`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ fontSize: 34, fontWeight: 800, marginRight: "auto" }}>For the family</div>
          <span style={{ fontSize: 22, fontWeight: 700, padding: "5px 12px", border: `2px solid ${C.blue}`, color: C.blue }}>AI-written</span>
          <span style={{ fontSize: 22, fontWeight: 700, padding: "5px 12px", border: `2px dashed ${C.muted}` }}>Simulated</span>
        </div>
        <div style={{ fontSize: 42, fontWeight: 500, lineHeight: 1.35, marginTop: 26 }}>
          {SUMMARY.slice(0, n)}
          <span
            style={{
              display: "inline-block",
              width: "0.45em",
              height: "0.95em",
              marginLeft: 4,
              verticalAlign: "-0.12em",
              background: C.led,
              opacity: typing ? (Math.floor(frame / 6) % 2 ? 0.25 : 1) : 0,
            }}
          />
        </div>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            marginTop: 26,
            padding: "10px 18px",
            border: `2px solid ${C.ink}`,
            fontSize: 24,
            fontWeight: 700,
            opacity: k(frame, [84, 92], [0, 1]),
          }}
        >
          <svg width={26} height={26} viewBox="0 0 26 26">
            <path d="M3 9 h5 l6 -5 v18 l-6 -5 h-5 z" fill={C.ink} />
            <path d="M18 8 q4 5 0 10" fill="none" stroke={C.ink} strokeWidth={2.5} />
          </svg>
          Listen, in Grok Voice
        </div>
      </div>
      {GUARDS.map(([text, at], i) => {
        const on = k(frame, [at, at + 6], [0, 1]);
        return (
          <div
            key={text}
            style={{
              position: "absolute",
              left: 1160,
              top: 440 + i * 116,
              width: 620,
              display: "flex",
              alignItems: "center",
              gap: 24,
              opacity: k(frame, [10 + i * 3, 18 + i * 3], [0, 1]),
              translate: `${k(frame, [10 + i * 3, 24 + i * 3], [40, 0], OUT)}px 0`,
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                flex: "none",
                border: `3px solid ${on > 0 ? C.greenLit : "rgba(255,255,255,0.3)"}`,
                background: on > 0 ? C.green : "transparent",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                scale: String(1 + pulse(frame, at, 5) * 0.15),
              }}
            >
              {on > 0 ? <Check size={44} progress={on} /> : null}
            </div>
            <div style={{ fontSize: 38, fontWeight: 700, color: on > 0 ? "#fff" : C.onDarkMuted, lineHeight: 1.15 }}>{text}</div>
          </div>
        );
      })}
    </Backdrop>
  );
};
