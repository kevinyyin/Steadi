import React from "react";
import { AbsoluteFill, Easing, Interactive, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, gait, Led, Ripples, trace, Words } from "../Kit";
import { C, INOUT, k, pulse } from "../theme";

// A single LED blinks on the beat, then drags a live lower-back signal across the frame.
export const ColdOpen: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const x0 = 140;
  const x1 = 1780;
  const midY = 540;
  const amp = 150;
  const windowS = 3.2;
  const draw = k(frame, [62, 118], [0, 1], INOUT);
  const scroll = Math.max(0, frame - 62) / fps;
  const env = (u: number) => Math.min(1, u * 12);
  const penX = x0 + (x1 - x0) * draw;
  const dotX = frame < 50 ? 960 : frame < 62 ? k(frame, [50, 62], [960, x0], INOUT) : penX;
  const dotY = frame < 62 ? 540 : midY - amp * env(draw) * gait(scroll);
  const beats = [0, 15, 30, 45];
  const beat = beats.reduce((m, b) => Math.max(m, pulse(frame, b, 5)), 0);

  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.045)">
      <AbsoluteFill style={{ opacity: k(frame, [60, 90], [0, 1]) }}>
        <svg width={1920} height={1080} style={{ position: "absolute" }}>
          <line x1={x0} x2={x1} y1={midY + 230} y2={midY + 230} stroke="rgba(255,255,255,0.18)" strokeWidth={2} />
          {Array.from({ length: 33 }, (_, i) => {
            const x = x0 + ((((i * 50 - (frame - 62) * 6) % 1650) + 1650) % 1650);
            return (
              <line
                key={i}
                x1={x}
                x2={x}
                y1={midY + 230}
                y2={midY + (i % 4 === 0 ? 252 : 242)}
                stroke="rgba(255,255,255,0.3)"
                strokeWidth={2}
              />
            );
          })}
        </svg>
      </AbsoluteFill>
      {frame >= 62 ? (
        <svg width={1920} height={1080} style={{ position: "absolute", filter: `drop-shadow(0 0 14px ${C.led})` }}>
          <path
            d={trace(x0, penX, 240, (u) => midY - amp * env(u * draw) * gait(scroll - (1 - u) * windowS * draw))}
            fill="none"
            stroke={C.led}
            strokeWidth={5}
            strokeLinejoin="round"
          />
        </svg>
      ) : null}
      <Ripples x={960} y={540} at={beats} max={320} />
      <Led
        x={dotX}
        y={dotY}
        r={15}
        glow={1 + beat * 0.8}
        scale={k(frame, [0, 10], [0, 1], Easing.spring({ damping: 10 })) * (1 + beat * 0.35)}
      />
      <Interactive.Div
        name="Headline"
        from={120}
        style={{ position: "absolute", left: 140, top: 130, fontSize: 150, fontWeight: 800, fontStretch: "112%", color: "#ffffff", lineHeight: 1 }}
      >
        <Words text="This is a walk." start={2} stagger={4} />
      </Interactive.Div>
      <Interactive.Div
        name="Subline"
        from={130}
        style={{ position: "absolute", left: 140, top: 850, fontSize: 72, fontWeight: 600, color: "#b9bdcc" }}
      >
        <Words text="Lower back. 100 times a second." start={2} stagger={3} />
      </Interactive.Div>
    </Backdrop>
  );
};
