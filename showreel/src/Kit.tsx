import { noise2D } from "@remotion/noise";
import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { C, FONT, IN, k } from "./theme";

/** Flat colour, an optional drifting grid, a vignette and film grain. */
export const Backdrop: React.FC<{
  color: string;
  grid?: string;
  size?: number;
  major?: string;
  drift?: number;
  children?: React.ReactNode;
}> = ({ color, grid, size = 120, major, drift = 0.4, children }) => {
  const f = useCurrentFrame();
  const lines = (c: string, s: number) =>
    `linear-gradient(${c} 1px, transparent 1px) 0 0 / ${s}px ${s}px, linear-gradient(90deg, ${c} 1px, transparent 1px) 0 0 / ${s}px ${s}px`;
  return (
    <AbsoluteFill style={{ backgroundColor: color, fontFamily: FONT, overflow: "hidden" }}>
      {grid ? (
        <AbsoluteFill
          style={{
            background: [major ? lines(major, size * 5) : "", lines(grid, size)].filter(Boolean).join(", "),
            translate: `${(-f * drift) % size}px ${(-f * drift * 0.5) % size}px`,
            inset: -size * 5,
          }}
        />
      ) : null}
      <AbsoluteFill
        style={{ background: "radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.28) 100%)" }}
      />
      {children}
    </AbsoluteFill>
  );
};

/** Moving film grain; sits above everything. */
export const Grain: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity: 0.07, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <svg width="1920" height="1080">
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={Math.floor(f / 2) % 7} stitchTiles="stitch" />
        </filter>
        <rect width="1920" height="1080" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
};

/** Words rise out of a mask, one after another. `\n` breaks a line. */
export const Words: React.FC<{
  text: string;
  start: number;
  stagger?: number;
  dur?: number;
  exit?: number;
  align?: "flex-start" | "center" | "flex-end";
  style?: React.CSSProperties;
  color?: (word: string, i: number) => string | undefined;
}> = ({ text, start, stagger = 3, dur = 20, exit, align = "flex-start", style, color }) => {
  const f = useCurrentFrame();
  let n = 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: align, ...style }}>
      {text.split("\n").map((line, li) => (
        <div key={li} style={{ display: "flex", columnGap: "0.26em", flexWrap: "wrap", justifyContent: align }}>
          {line.split(" ").map((w) => {
            const i = n++;
            const s = start + i * stagger;
            const y =
              k(f, [s, s + dur], [115, 0]) + (exit === undefined ? 0 : k(f, [exit + i * 2, exit + i * 2 + 14], [0, -115], IN));
            return (
              <span key={i} style={{ display: "inline-block", overflow: "hidden", padding: "0.06em 0.04em 0.14em", margin: "-0.06em -0.04em -0.14em" }}>
                <span style={{ display: "inline-block", translate: `0 ${y}%`, color: color?.(w, i) }}>{w}</span>
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

/** Odometer digits: the last digit spins (or ticks, with `snap`), higher digits roll over on carry.
 * Leading zeros collapse to nothing and grow in as they roll up. */
export const Rolling: React.FC<{
  value: number;
  decimals?: number;
  digits?: number;
  snap?: boolean;
  style?: React.CSSProperties;
}> = ({ value, decimals = 0, digits = 1, snap, style }) => {
  const scaled = Math.max(0, value) * 10 ** decimals;
  const places = Math.max(digits + decimals, String(Math.floor(scaled + 1e-6)).length);
  const cols: React.ReactNode[] = [];
  for (let p = places - 1; p >= 0; p--) {
    const v = scaled / 10 ** p;
    const lower = p === 0 ? 0 : (scaled % 10 ** p) / 10 ** p;
    const pos = p === 0 ? (snap ? Math.floor(v % 10) : v % 10) : (Math.floor(v) % 10) + Math.max(0, (lower - 0.9) * 10);
    const grow = p > decimals && v < 1 ? Math.min(1, pos) : 1;
    cols.push(
      <span key={p} style={{ display: "inline-block", height: "1.1em", overflow: "hidden", opacity: grow, maxWidth: `${grow}em` }}>
        <span style={{ display: "block", translate: `0 ${-pos * 1.1}em` }}>
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map((d, i) => (
            <span key={i} style={{ display: "block", height: "1.1em", lineHeight: "1.1em" }}>
              {d}
            </span>
          ))}
        </span>
      </span>,
    );
    if (p === decimals && decimals > 0) cols.push(<span key="dot">.</span>);
  }
  return (
    <span style={{ display: "inline-flex", fontVariantNumeric: "tabular-nums", lineHeight: "1.1em", ...style }}>{cols}</span>
  );
};

/** The belt's status LED: a glowing dot. */
export const Led: React.FC<{ x: number; y: number; r?: number; color?: string; glow?: number; scale?: number; opacity?: number }> = ({
  x,
  y,
  r = 14,
  color = C.led,
  glow = 1,
  scale = 1,
  opacity = 1,
}) => (
  <div
    style={{
      position: "absolute",
      left: x - r,
      top: y - r,
      width: r * 2,
      height: r * 2,
      borderRadius: "50%",
      background: `radial-gradient(circle at 40% 35%, #ffffff 0%, ${color} 45%)`,
      boxShadow: `0 0 ${24 * glow}px ${6 * glow}px ${color}cc, 0 0 ${90 * glow}px ${30 * glow}px ${color}55`,
      scale: String(scale),
      opacity,
    }}
  />
);

/** Ripple rings leaving a point on each listed frame. */
export const Ripples: React.FC<{ x: number; y: number; at: number[]; color?: string; max?: number; life?: number }> = ({
  x,
  y,
  at,
  color = C.led,
  max = 260,
  life = 30,
}) => {
  const f = useCurrentFrame();
  return (
    <>
      {at.map((a) => {
        if (f < a || f > a + life) return null;
        const r = k(f, [a, a + life], [18, max]);
        return (
          <div
            key={a}
            style={{
              position: "absolute",
              left: x - r,
              top: y - r,
              width: r * 2,
              height: r * 2,
              borderRadius: "50%",
              border: `3px solid ${color}`,
              opacity: k(f, [a, a + life], [0.7, 0]),
            }}
          />
        );
      })}
    </>
  );
};

/** "Simulated" label, as the dashboard shows it: every simulated value carries one. */
export const Simulated: React.FC<{ dark?: boolean; style?: React.CSSProperties }> = ({ dark, style }) => (
  <div
    style={{
      display: "inline-block",
      padding: "6px 14px",
      border: `2px dashed ${dark ? "rgba(255,255,255,0.7)" : C.muted}`,
      color: dark ? "#fff" : C.ink,
      fontSize: 28,
      fontWeight: 700,
      letterSpacing: "0.01em",
      ...style,
    }}
  >
    Simulated
  </div>
);

/** An instruction picture from the dashboard, graded cool so it sits in the palette. */
export const Picture: React.FC<{ src: string; w: number; h: number; tint?: string; style?: React.CSSProperties }> = ({
  src,
  w,
  h,
  tint = C.blueSoft,
  style,
}) => (
  <div style={{ position: "relative", width: w, height: h, overflow: "hidden", background: "#fff", ...style }}>
    <Img
      src={staticFile(`img/${src}`)}
      style={{ width: "100%", height: "100%", objectFit: "cover", filter: "grayscale(1) contrast(1.12) brightness(1.06)" }}
    />
    <div style={{ position: "absolute", inset: 0, background: tint, mixBlendMode: "multiply", opacity: 0.75 }} />
  </div>
);

/** Walking-like lower-back acceleration: ~1.9 steps a second plus harmonics and a little noise. */
export const gait = (t: number, seed = "gait") => {
  const w = 2 * Math.PI * 1.9;
  return (
    0.55 * Math.sin(w * t) +
    0.24 * Math.sin(2 * w * t + 0.6) +
    0.12 * Math.sin(3 * w * t + 1.3) +
    0.2 * noise2D(seed, t * 5, 0)
  );
};

/** SVG path through `n` samples of `fn` over x in [x0, x1]. */
export const trace = (x0: number, x1: number, n: number, fn: (u: number) => number) => {
  let d = "";
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    d += `${i ? "L" : "M"}${(x0 + (x1 - x0) * u).toFixed(1)} ${fn(u).toFixed(1)}`;
  }
  return d;
};

/** A check mark that draws on with `progress`. */
export const Check: React.FC<{ size?: number; color?: string; progress?: number }> = ({ size = 40, color = "#fff", progress = 1 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40">
    <path
      d="M8 21 L17 30 L33 11"
      fill="none"
      stroke={color}
      strokeWidth={5}
      strokeLinecap="square"
      strokeDasharray={40}
      strokeDashoffset={40 * (1 - progress)}
    />
  </svg>
);

