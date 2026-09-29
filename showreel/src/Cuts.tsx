import { lightLeak } from "@remotion/effects/light-leak";
import React from "react";
import { AbsoluteFill, interpolate, Solid, useCurrentFrame, useVideoConfig } from "remotion";
import { IN, k, OUT } from "./theme";

// Overlays that sit on a cut without shortening the timeline, so every scene still starts on the bar.

/** A white bloom that peaks on the cut. */
export const Flash: React.FC<{ color?: string }> = ({ color = "#ffffff" }) => {
  const frame = useCurrentFrame();
  const { durationInFrames: d } = useVideoConfig();
  return <AbsoluteFill style={{ background: color, opacity: k(frame, [0, d / 2, d], [0, 0.9, 0]) }} />;
};

/** Vertical bars close over the outgoing scene, the cut happens behind them, then they open. */
export const Shutter: React.FC<{ colors: string[]; bars?: number }> = ({ colors, bars = 8 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames: d } = useVideoConfig();
  const mid = d / 2;
  return (
    <AbsoluteFill style={{ flexDirection: "row" }}>
      {Array.from({ length: bars }, (_, i) => {
        const s = i * 0.6;
        const closing = frame < mid;
        const v = closing ? k(frame, [s, s + mid - 0.6 * bars + 0.6], [0, 1], IN) : k(frame, [mid + s, mid + s + mid - 0.6 * bars + 0.6], [1, 0], OUT);
        return (
          <div
            key={i}
            style={{
              flex: 1,
              background: colors[i % colors.length],
              scale: `1 ${v}`,
              transformOrigin: closing ? "top" : "bottom",
              marginRight: -1,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/** A slanted panel sweeps across; it fully covers the frame on the cut. */
export const Wipe: React.FC<{ color: string }> = ({ color }) => {
  const frame = useCurrentFrame();
  const { durationInFrames: d } = useVideoConfig();
  const x = interpolate(frame, [0, d / 2, d], [-140, 0, 140], { easing: IN, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: "-10% -30%", background: color, transform: `translateX(${x}%) skewX(-14deg)` }} />
    </AbsoluteFill>
  );
};

/** Remotion's light leak, rotated into the LED blue. */
export const Leak: React.FC<{ seed?: number; hueShift?: number }> = ({ seed = 3, hueShift = 190 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, height, width } = useVideoConfig();
  return (
    <Solid
      width={width}
      height={height}
      effects={[
        lightLeak({
          seed,
          hueShift,
          progress: interpolate(frame, [0, durationInFrames - 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }),
      ]}
    />
  );
};
