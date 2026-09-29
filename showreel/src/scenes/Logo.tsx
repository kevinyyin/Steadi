import React from "react";
import { AbsoluteFill, Interactive, useCurrentFrame } from "remotion";
import { Backdrop, Led, Ripples, trace, Words } from "../Kit";
import { noise2D } from "@remotion/noise";
import { C, IN, INOUT, k, pulse } from "../theme";

/** "Steadı" with the belt's LED as the dot on the i. Letters rise out of the line they sit on. */
export const Wordmark: React.FC<{ start: number; size?: number; exit?: number; land?: number }> = ({ start, size = 300, exit, land }) => {
  const frame = useCurrentFrame();
  const drop = land ?? start + 30;
  const fallen = k(frame, [drop - 14, drop], [0, 1], IN);
  const squash = pulse(frame, drop, 4);
  const gone = exit === undefined ? 0 : k(frame, [exit, exit + 12], [0, 1], IN);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        fontSize: size,
        fontWeight: 900,
        fontStretch: `${k(frame, [start, start + 34], [70, 112])}%`,
        lineHeight: 0.78,
        color: "#fff",
        letterSpacing: "-0.012em",
      }}
    >
      {["S", "t", "e", "a", "d", "ı"].map((ch, i) => {
        const s = start + i * 3;
        const y = k(frame, [s, s + 20], [110, 0]) + (exit === undefined ? 0 : k(frame, [exit + i * 2, exit + i * 2 + 14], [0, 110], IN));
        return (
          <span key={i} style={{ position: "relative", display: "inline-block" }}>
            <span style={{ display: "inline-block", overflow: "hidden", verticalAlign: "bottom", paddingTop: "0.1em" }}>
              <span style={{ display: "inline-block", translate: `0 ${y}%` }}>{ch}</span>
            </span>
            {ch === "ı" ? (
              <span
                style={{
                  position: "absolute",
                  left: "50%",
                  bottom: "0.66em",
                  width: "0.15em",
                  height: "0.15em",
                  marginLeft: "-0.075em",
                  borderRadius: "50%",
                  background: `radial-gradient(circle at 40% 35%, #ffffff 0%, ${C.led} 50%)`,
                  boxShadow: `0 0 ${0.08 + squash * 0.1}em ${0.02 + squash * 0.03}em ${C.led}, 0 0 0.4em 0.08em ${C.led}66`,
                  translate: `0 ${(1 - fallen) * -3.2 + gone * 0.6}em`,
                  scale: `${1 + squash * 0.25} ${1 - squash * 0.3}`,
                  opacity: k(frame, [drop - 14, drop - 12], [0, 1]) * (1 - gone),
                }}
              />
            ) : null}
          </span>
        );
      })}
    </div>
  );
};

// The drop: a jittery signal calms into one steady line, and the name rises out of it.
export const Logo: React.FC = () => {
  const frame = useCurrentFrame();
  const lineY = 640;
  const amp = k(frame, [0, 30], [230, 0], INOUT);
  const half = k(frame, [22, 44], [960, 590], INOUT) * k(frame, [136, 156], [1, 0], INOUT);
  const collapse = k(frame, [150, 158], [0, 1]);
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 50% 60%, ${C.led}66 0%, transparent 55%)`,
          opacity: pulse(frame, 0, 12) + pulse(frame, 60, 10) * 0.5,
        }}
      />
      <div style={{ position: "absolute", left: 0, right: 0, top: lineY - 300 * 0.78 - 30, display: "flex", justifyContent: "center" }}>
        <Wordmark start={30} land={60} exit={118} />
      </div>
      {half > 0.5 ? (
        <svg width={1920} height={1080} style={{ position: "absolute", filter: `drop-shadow(0 0 16px ${C.led})` }}>
          <path
            d={trace(960 - half, 960 + half, 260, (u) => {
              const taper = Math.sin(Math.PI * u);
              return lineY + amp * taper * (0.7 * noise2D("drop", u * 18, frame * 0.35) + 0.3 * Math.sin(u * 90 + frame));
            })}
            fill="none"
            stroke={C.led}
            strokeWidth={8}
            strokeLinecap="square"
          />
        </svg>
      ) : null}
      <Ripples x={960} y={lineY} at={[0]} max={700} life={26} />
      <Interactive.Div
        name="Tagline"
        from={68}
        style={{ position: "absolute", left: 0, right: 0, top: lineY + 50, fontSize: 72, fontWeight: 600, color: "#ffffff", lineHeight: 1.12 }}
      >
        <Words text={"The CDC's fall-risk tests,\nscored by a belt at home."} start={0} stagger={2} align="center" exit={46} />
      </Interactive.Div>
      {collapse > 0 ? (
        <Led
          x={960}
          y={k(frame, [156, 176], [lineY, 540], INOUT)}
          r={15}
          scale={collapse * (1 + pulse(frame, 165, 5) * 0.3)}
          glow={1 + pulse(frame, 150, 8)}
        />
      ) : null}
    </Backdrop>
  );
};
