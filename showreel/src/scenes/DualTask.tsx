import React from "react";
import { AbsoluteFill, Easing, Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Ripples, Rolling, Simulated, Words } from "../Kit";
import { C, IN, k, pulse } from "../theme";

const ANIMALS: [string, number, number, number][] = [
  ["cat", 300, 400, -4],
  ["dog", 720, 470, 3],
  ["horse", 1150, 390, -2],
  ["zebra", 1560, 470, 5],
  ["owl", 420, 610, 4],
  ["tiger", 880, 660, -5],
  ["rabbit", 1300, 620, 2],
  ["goat", 1650, 700, -3],
  ["lion", 640, 770, 3],
];
const said = (i: number) => 14 + i * 8;
const COUNTER: [number, number] = [230, 900];

// The dual-task walk: the same TUG while naming animals. Names pop in on the beat, then fly into the count.
export const DualTask: React.FC = () => {
  const frame = useCurrentFrame();
  const count = ANIMALS.reduce((n, _, i) => n + k(frame, [said(i), said(i) + 6], [0, 1]), 0);
  return (
    <Backdrop color={C.blue} grid="rgba(255,255,255,0.06)" size={60}>
      <Interactive.Div name="Dual-task title" style={{ position: "absolute", left: 140, top: 130, color: "#ffffff" }}>
        <Words text="Same walk. Now name animals." start={0} stagger={2} style={{ fontSize: 96, fontWeight: 900, fontStretch: "106%", lineHeight: 1 }} />
        <Words
          text="Grok speech to text counts them, if the family opts in."
          start={8}
          stagger={1}
          style={{ fontSize: 40, fontWeight: 600, color: "#b3c1f4", marginTop: 18 }}
        />
      </Interactive.Div>
      <Simulated dark style={{ position: "absolute", right: 140, top: 262 }} />
      {ANIMALS.map(([w, x, y, rot], i) => {
        const a = said(i);
        if (frame < a) return null;
        const fly = k(frame, [92 + i * 1.5, 104 + i * 1.5], [0, 1], IN);
        return (
          <React.Fragment key={w}>
            <Ripples x={x} y={y} at={[a]} color="#ffffff" max={120} life={16} />
            <div
              style={{
                position: "absolute",
                left: x + (COUNTER[0] - x) * fly,
                top: y + (COUNTER[1] - y) * fly,
                translate: "-50% -50%",
                rotate: `${rot * (1 - fly)}deg`,
                scale: String(k(frame, [a, a + 10], [0.3, 1], Easing.spring({ damping: 9 })) * (1 - fly * 0.8)),
                opacity: 1 - k(frame, [98 + i * 1.5, 104 + i * 1.5], [0, 1]),
                fontSize: 92,
                fontWeight: 800,
                fontStretch: "110%",
                color: i % 3 === 1 ? C.led : "#fff",
                whiteSpace: "nowrap",
              }}
            >
              {w}
            </div>
          </React.Fragment>
        );
      })}
      <AbsoluteFill>
        <div style={{ position: "absolute", left: 140, top: 790, color: "#fff", opacity: k(frame, [10, 18], [0, 1]) }}>
          <div style={{ fontSize: 36, fontWeight: 700, color: C.blueSoft }}>Animals named</div>
          <div style={{ fontSize: 130, fontWeight: 900, lineHeight: 1, scale: String(1 + pulse(frame, 104, 6) * 0.12), transformOrigin: "left center" }}>
            <Rolling value={count} digits={1} />
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            right: 140,
            top: 790,
            textAlign: "right",
            color: "#fff",
            opacity: k(frame, [56, 64], [0, 1]),
            translate: `0 ${k(frame, [56, 70], [30, 0])}px`,
          }}
        >
          <div style={{ fontSize: 36, fontWeight: 700, color: C.blueSoft }}>Dual-task cost, tracked against baseline</div>
          <div style={{ fontSize: 130, fontWeight: 900, lineHeight: 1 }}>
            +<Rolling value={k(frame, [58, 84], [0, 17])} digits={2} />%
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
