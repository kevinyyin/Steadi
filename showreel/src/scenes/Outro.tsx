import React from "react";
import { AbsoluteFill, Interactive, Sequence, useCurrentFrame } from "remotion";
import { CameraMotionBlur } from "@remotion/motion-blur";
import { Backdrop, Led, Words } from "../Kit";
import { Wordmark } from "./Logo";
import { C, IN, INOUT, k, pulse } from "../theme";

const Slam: React.FC<{ word: string; bg: string; fg: string }> = ({ word, bg, fg }) => {
  return (
    <AbsoluteFill style={{ background: bg, justifyContent: "center", alignItems: "center" }}>
      <CameraMotionBlur samples={6} shutterAngle={200}>
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
          <SlamWord word={word} fg={fg} />
        </AbsoluteFill>
      </CameraMotionBlur>
    </AbsoluteFill>
  );
};

const SlamWord: React.FC<{ word: string; fg: string }> = ({ word, fg }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        fontSize: 330,
        fontWeight: 900,
        fontStretch: `${k(frame, [0, 8], [70, 125])}%`,
        color: fg,
        lineHeight: 1,
        scale: String(k(frame, [0, 7], [1.35, 1])),
        translate: `0 ${k(frame, [0, 7], [60, 0])}px`,
        letterSpacing: "-0.02em",
      }}
    >
      {word}
    </div>
  );
};

// Check. Coach. Share. on three beats, then the wordmark, the credits, and the LED going out.
export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const fade = k(frame, [150, 164], [1, 0], INOUT);
  const blink = frame >= 166 && frame < 178 ? pulse(frame, 166, 3) + pulse(frame, 172, 3) : 0;
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.035)">
      <Sequence  durationInFrames={15} name="Check.">
        <Slam word="Check." bg={C.blue} fg="#ffffff" />
      </Sequence>
      <Sequence from={15} durationInFrames={15} name="Coach.">
        <Slam word="Coach." bg={C.paper} fg={C.ink} />
      </Sequence>
      <Sequence from={30} durationInFrames={15} name="Share.">
        <Slam word="Share." bg={C.ink} fg={C.led} />
      </Sequence>
      <Sequence from={45} durationInFrames={17} name="All three">
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
          <Words
            text="Check. Coach. Share."
            start={0}
            stagger={3}
            exit={10}
            align="center"
            color={(w) => (w === "Share." ? C.led : undefined)}
            style={{ fontSize: 150, fontWeight: 900, fontStretch: "112%", color: "#fff" }}
          />
        </AbsoluteFill>
      </Sequence>
      <Sequence from={58} name="End card">
        <AbsoluteFill style={{ opacity: fade }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: 560 - 300 * 0.78 - 30, display: "flex", justifyContent: "center" }}>
            <Wordmark start={4} land={32} />
          </div>
          <div
            style={{
              position: "absolute",
              top: 556,
              left: 960 - 590 * k(frame - 58, [0, 14], [0, 1], INOUT),
              width: 1180 * k(frame - 58, [0, 14], [0, 1], INOUT),
              height: 8,
              background: C.led,
              boxShadow: `0 0 18px ${C.led}`,
            }}
          />
          <Interactive.Div name="End tagline" from={34} style={{ position: "absolute", left: 0, right: 0, top: 612, color: "#ffffff", textAlign: "center" }}>
            <Words text="Fall-risk screening at home." start={0} stagger={2} align="center" style={{ fontSize: 68, fontWeight: 700 }} />
            <Words
              text="It flags increased fall risk. It does not diagnose."
              start={8}
              stagger={1}
              align="center"
              style={{ fontSize: 34, fontWeight: 600, color: "#b9bdcc", marginTop: 14 }}
            />
          </Interactive.Div>
          <Interactive.Div
            name="Credits"
            from={56}
            style={{ position: "absolute", left: 0, right: 0, top: 830, textAlign: "center", fontSize: 36, fontWeight: 700, color: "#ffffff" }}
          >
            <Words text="Steadi by dhsquad, HackGT 13" start={0} stagger={1} align="center" />
            <Words text="dhsquad.onrender.com" start={4} align="center" style={{ color: "#3aa0ff", marginTop: 8 }} />
          </Interactive.Div>
        </AbsoluteFill>
      </Sequence>
      {frame >= 160 ? <Led x={960} y={540} r={15} opacity={k(frame, [160, 164], [0, 1]) * (frame >= 178 ? 0 : 1)} glow={0.6 + blink} scale={0.8 + blink * 0.4} /> : null}
      <AbsoluteFill style={{ background: "#000", opacity: k(frame, [176, 180], [0, 1], IN) }} />
    </Backdrop>
  );
};
