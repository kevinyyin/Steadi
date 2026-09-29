import { loadFont } from "@remotion/fonts";
import { Easing, interpolate, staticFile } from "remotion";

// Steadi's own tokens (src/checkin/static/index.html) and its vendored variable Archivo (wght 100–900, wdth 62–125).
loadFont({
  family: "Archivo",
  url: staticFile("archivo.woff2"),
  weight: "100 900",
  stretch: "62% 125%",
});

export const FONT = "Archivo";

export const C = {
  ink: "#080912",
  inkRaised: "#151a30",
  blue: "#2a4093",
  blueSoft: "#b3c1f4",
  led: "#3aa0ff",
  ground: "#eef0f4",
  paper: "#ffffff",
  muted: "#464b5d",
  line: "#cdd1db",
  onDarkMuted: "#b9bdcc",
  green: "#136c34",
  greenLit: "#34c46a", // green on dark backgrounds
  amber: "#f2a900",
  red: "#b42318",
};

// 120 BPM at 30 fps: every cut and cue sits on this grid, and scripts/make_music.py uses the same one.
export const BEAT = 15;
export const BAR = 60;

export const OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const INOUT = Easing.bezier(0.65, 0, 0.35, 1);
export const IN = Easing.bezier(0.7, 0, 0.84, 0);
export const SPRING = Easing.spring({ damping: 12 });

/** Clamped interpolate for computed (non-Studio-editable) motion. */
export const k = (
  f: number,
  input: number[],
  output: number[],
  easing: (t: number) => number = OUT,
) =>
  interpolate(f, input, output, {
    easing,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

/** 1 at `at`, decaying exponentially after it; 0 before. */
export const pulse = (f: number, at: number, decay = 6) =>
  f < at ? 0 : Math.exp(-(f - at) / decay);
