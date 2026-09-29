import React from "react";
import { AbsoluteFill, Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Words } from "../Kit";
import { C, IN, INOUT, k, OUT } from "../theme";

const PANELS = [
  { name: "Green", sub: "No flags", bg: C.green, fg: "#fff" },
  { name: "Amber", sub: "1 flag, or a decline", bg: C.amber, fg: C.ink },
  { name: "Red", sub: "2 or more flags", bg: C.red, fg: "#fff" },
];

// The three levels slam up on the beat, amber takes the frame, then shrinks back into an LED.
export const Levels: React.FC = () => {
  const frame = useCurrentFrame();
  const squeeze = k(frame, [34, 54], [1, 0], INOUT);
  const shrink = k(frame, [100, 118], [0, 1], IN);
  return (
    <Backdrop color={C.ink}>
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "row",
          clipPath: `inset(${shrink * 515}px ${shrink * 935}px round ${shrink * 30}px)`,
          boxShadow: `0 0 120px ${C.amber}`,
        }}
      >
        {PANELS.map((p, i) => {
          const up = k(frame, [i * 5, i * 5 + 14], [100, 0], OUT);
          const amber = i === 1;
          return (
            <div
              key={p.name}
              style={{
                flex: `${amber ? 1 : squeeze} 1 0px`,
                background: p.bg,
                color: p.fg,
                overflow: "hidden",
                translate: `0 ${up}%`,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                whiteSpace: "nowrap",
              }}
            >
              <div style={{ opacity: amber ? k(frame, [40, 48], [1, 0]) : 1, textAlign: "center" }}>
                <div style={{ fontSize: 124, fontWeight: 900, fontStretch: `${k(frame, [i * 5, i * 5 + 24], [70, 118])}%` }}>{p.name}</div>
                <div style={{ fontSize: 40, fontWeight: 700, marginTop: 8 }}>{p.sub}</div>
              </div>
            </div>
          );
        })}
      </AbsoluteFill>
      <Interactive.Div
        name="Amber message"
        from={52}
        style={{ position: "absolute", left: 0, right: 0, top: 330, color: "#080912", textAlign: "center", opacity: 1 - shrink }}
      >
        <Words text="Flags increased fall risk." start={0} stagger={3} align="center" style={{ fontSize: 130, fontWeight: 900, fontStretch: "104%", lineHeight: 1 }} />
        <Words
          text={"Our own summary of the STEADI flags,\nplus change from baseline. The lights show it too."}
          start={10}
          stagger={1}
          align="center"
          style={{ fontSize: 48, fontWeight: 650, marginTop: 40, lineHeight: 1.25 }}
        />
      </Interactive.Div>
    </Backdrop>
  );
};
