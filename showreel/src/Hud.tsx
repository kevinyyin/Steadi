import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { BEAT, FONT, k, pulse } from "./theme";

// Showreel furniture: crop marks, a beat LED, timecode, and what each section shows off.
// White with a difference blend so it reads on the ink, blue and white scenes alike.
const CHAPTERS: [number, string, string][] = [
  [0, "Signal", "Procedural signal, noise-driven"],
  [180, "The problem", "Kinetic type, odometer digits"],
  [420, "Brand", "Variable-font width animation"],
  [600, "STEADI loop", "Path draw, orbit, zoom-through"],
  [780, "Hardware", "Isometric exploded view"],
  [1020, "Check: Timed Up and Go", "Live data UI"],
  [1200, "Check: dual task", "Spring pops, gather"],
  [1320, "Check: chair stand", "Radial timer, syncopated reps"],
  [1500, "Check: balance", "Sway plot"],
  [1680, "Fall-risk level", "Flex morph, clip-path"],
  [1800, "Coach", "Segmented progress"],
  [1980, "Share", "3D camera on real UI"],
  [2220, "Grok summary", "Typewriter, checklist"],
  [2340, "End", "Motion blur, logo resolve"],
];

const Mark: React.FC<{ x: number; y: number; sx: number; sy: number }> = ({ x, y, sx, sy }) => (
  <div style={{ position: "absolute", left: x, top: y, width: 34, height: 34, borderLeft: sx > 0 ? "2px solid #fff" : undefined, borderRight: sx < 0 ? "2px solid #fff" : undefined, borderTop: sy > 0 ? "2px solid #fff" : undefined, borderBottom: sy < 0 ? "2px solid #fff" : undefined }} />
);

export const Hud: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const [start, name, craft] = CHAPTERS.filter(([s]) => frame >= s).pop()!;
  const tc = [Math.floor(frame / fps / 60), Math.floor(frame / fps) % 60, frame % fps].map((n) => String(n).padStart(2, "0")).join(":");
  const beat = pulse(frame, Math.floor(frame / BEAT) * BEAT, 4);
  const inn = k(frame, [start, start + 10], [0, 1]);
  return (
    <AbsoluteFill
      style={{
        mixBlendMode: "difference",
        color: "#fff",
        fontFamily: FONT,
        fontSize: 22,
        fontWeight: 650,
        letterSpacing: "0.01em",
        opacity: 0.55 * k(frame, [4, 20], [0, 1]) * k(frame, [durationInFrames - 30, durationInFrames - 14], [1, 0]),
        pointerEvents: "none",
      }}
    >
      <Mark x={40} y={40} sx={1} sy={1} />
      <Mark x={1846} y={40} sx={-1} sy={1} />
      <Mark x={40} y={1006} sx={1} sy={-1} />
      <Mark x={1846} y={1006} sx={-1} sy={-1} />
      <div style={{ position: "absolute", left: 92, top: 44, display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#fff", opacity: 0.35 + beat * 0.65 }} />
        Motion reel 2026
      </div>
      <div style={{ position: "absolute", right: 92, top: 44, fontVariantNumeric: "tabular-nums" }}>{tc}</div>
      <div style={{ position: "absolute", left: 92, bottom: 44, opacity: inn, translate: `0 ${(1 - inn) * 10}px` }}>{name}</div>
      <div style={{ position: "absolute", right: 92, bottom: 44, opacity: inn, translate: `0 ${(1 - inn) * 10}px` }}>{craft}</div>
    </AbsoluteFill>
  );
};
