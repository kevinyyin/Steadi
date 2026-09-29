import React from "react";
import { Easing, Interactive, useCurrentFrame } from "remotion";
import { noise2D } from "@remotion/noise";
import { Backdrop, Check, Picture, Rolling, Simulated, Words } from "../Kit";
import { C, k, OUT, pulse } from "../theme";

const STANCES = [
  { img: "feet_together.jpg", label: "Feet together" },
  { img: "semi_tandem.jpg", label: "One foot a little ahead" },
  { img: "tandem.jpg", label: "One foot right in front" },
];
const W = 500;
const H = 375;
const X = [140, 710, 1280];
const TOP = 250;
const win = (i: number): [number, number] => [16 + i * 50, 16 + i * 50 + 48];
export const SWAY_WARN = 142;

// Balance: three stances, 10 s each; a top-down sway plot trips a warning on the hardest one.
export const Balance: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Backdrop color={C.paper} grid="rgba(8,9,18,0.045)">
      <Interactive.Div name="Balance title" style={{ position: "absolute", left: 140, top: 110, color: "#080912" }}>
        <Words text="Three stances. 10 seconds each." start={0} stagger={2} style={{ fontSize: 84, fontWeight: 900, fontStretch: "104%", lineHeight: 1 }} />
      </Interactive.Div>
      <Simulated style={{ position: "absolute", right: 140, top: 198 }} />
      {STANCES.map((s, i) => {
        const [a, b] = win(i);
        const hold = k(frame, [a, b], [0, 10], Easing.linear);
        const active = frame >= a && frame < b + 4;
        const done = frame >= b;
        const inn = k(frame, [i * 4, i * 4 + 18], [0, 1], OUT);
        const focus = k(frame, [a - 6, a + 4], [0, 1]) * k(frame, [b, b + 8], [1, 0]);
        return (
          <div
            key={s.img}
            style={{
              position: "absolute",
              left: X[i],
              top: TOP,
              width: W,
              opacity: inn * (active ? 1 : done ? 0.85 : 0.5),
              translate: `0 ${(1 - inn) * 60}px`,
            }}
          >
            <div style={{ position: "relative", scale: String(1 + focus * 0.04), outline: `${5 * focus}px solid ${C.led}`, outlineOffset: 6 }}>
              <Picture src={s.img} w={W} h={H} />
              {focus > 0 ? <Sway i={i} opacity={focus} /> : null}
            </div>
            <div style={{ fontSize: 34, fontWeight: 800, color: C.ink, marginTop: 26 }}>{s.label}</div>
            <div style={{ height: 12, background: C.line, marginTop: 14, position: "relative" }}>
              <div style={{ position: "absolute", inset: 0, width: `${hold * 10}%`, background: done ? C.green : C.blue }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 12, fontSize: 48, fontWeight: 900, color: done ? C.green : C.ink }}>
              <Rolling value={hold} decimals={1} snap /> s
              {done ? <Check size={46} color={C.green} progress={k(frame, [b, b + 10], [0, 1])} /> : null}
            </div>
          </div>
        );
      })}
      <Interactive.Div name="Balance note" style={{ position: "absolute", left: 140, top: 860, color: "#464b5d", fontSize: 44, fontWeight: 600, lineHeight: 1.2 }}>
        <Words text={"Sway beeps a warning first.\nDone beside a counter, with someone standing by."} start={24} stagger={1} />
      </Interactive.Div>
    </Backdrop>
  );
};

/** Top-down sway: where the lower back drifts over the feet. Warning ring flashes amber when crossed. */
const Sway: React.FC<{ i: number; opacity: number }> = ({ i, opacity }) => {
  const frame = useCurrentFrame();
  const size = 160;
  const c = size / 2;
  const amp = [10, 16, 24][i];
  const kick = i === 2 ? Math.exp(-(((frame - SWAY_WARN) / 7) ** 2)) * 34 : 0;
  const pos = (f: number): [number, number] => [
    c + amp * noise2D("sx" + i, f * 0.05, 0) + kick * 0.9,
    c + amp * noise2D("sy" + i, 0, f * 0.05) - kick * 0.4,
  ];
  const pts = Array.from({ length: 24 }, (_, j) => pos(frame - j));
  const warn = i === 2 ? pulse(frame, SWAY_WARN - 2, 10) : 0;
  return (
    <div style={{ position: "absolute", right: 16, top: 16, opacity }}>
      <svg width={size} height={size} style={{ background: "rgba(8,9,18,0.82)", display: "block" }}>
        <circle cx={c} cy={c} r={22} fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth={2} />
        <circle cx={c} cy={c} r={48} fill="none" stroke={warn > 0.05 ? C.amber : "rgba(255,255,255,0.45)"} strokeWidth={3 + warn * 5} />
        <circle cx={c} cy={c} r={70} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth={2} />
        <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={C.led} strokeWidth={3} opacity={0.7} />
        <circle cx={pts[0][0]} cy={pts[0][1]} r={7} fill="#fff" />
      </svg>
      {i === 2 ? (
        <div
          style={{
            position: "absolute",
            right: 0,
            top: size + 8,
            padding: "6px 12px",
            background: C.amber,
            color: C.ink,
            fontSize: 26,
            fontWeight: 800,
            whiteSpace: "nowrap",
            opacity: k(frame, [SWAY_WARN - 3, SWAY_WARN], [0, 1]) * k(frame, [SWAY_WARN + 18, SWAY_WARN + 24], [1, 0]),
          }}
        >
          Sway warning
        </div>
      ) : null}
    </div>
  );
};
