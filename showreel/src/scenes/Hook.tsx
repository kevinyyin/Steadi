import React from "react";
import { AbsoluteFill, Interactive, Sequence, useCurrentFrame } from "remotion";
import { Backdrop, Rolling, Words } from "../Kit";
import { C, IN, INOUT, k, OUT } from "../theme";

// Three numbers, one bar each: the problem, the evidence, the gap. Then the pivot line.
const Stat: React.FC<{ big: React.ReactNode; caption: string; source: string }> = ({ big, caption, source }) => {
  const frame = useCurrentFrame();
  const out = k(frame, [48, 60], [0, 1], IN);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 130,
          top: 170,
          fontSize: 380,
          fontWeight: 900,
          fontStretch: `${k(frame, [0, 26], [62, 125])}%`,
          letterSpacing: "-0.02em",
          lineHeight: 1,
          color: "#fff",
          whiteSpace: "nowrap",
          opacity: k(frame, [0, 5], [0, 1]) * (1 - out),
          translate: `0 ${k(frame, [0, 18], [90, 0]) - out * 160}px`,
          scale: String(k(frame, [0, 18], [1.14, 1])),
          transformOrigin: "left center",
          filter: `blur(${k(frame, [0, 10], [22, 0]) + out * 18}px)`,
        }}
      >
        {big}
      </div>
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 650,
          height: 12,
          width: k(frame, [4, 30], [0, 560]) * (1 - out),
          background: C.led,
          boxShadow: `0 0 24px ${C.led}`,
        }}
      />
      <Words
        text={caption}
        start={8}
        stagger={3}
        exit={46}
        style={{ position: "absolute", left: 140, top: 700, fontSize: 76, fontWeight: 650, color: "#fff", maxWidth: 1600, lineHeight: 1.1 }}
      />
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 930,
          fontSize: 30,
          fontWeight: 600,
          color: "rgba(255,255,255,0.55)",
          opacity: k(frame, [14, 24], [0, 1]) * (1 - out),
        }}
      >
        {source}
      </div>
    </AbsoluteFill>
  );
};

const Count: React.FC<{ to: number }> = ({ to }) => {
  const frame = useCurrentFrame();
  return (
    <>
      <Rolling value={k(frame, [0, 26], [0, to], OUT)} digits={2} />%
    </>
  );
};

export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const swap = k(frame, [214, 224], [0, 1], OUT);
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <Sequence  durationInFrames={60} name="1 in 4">
        <Stat big="1 in 4" caption="adults 65 and older report a fall each year." source="CDC" />
      </Sequence>
      <Sequence from={60} durationInFrames={60} name="23%">
        <Stat big={<Count to={23} />} caption="fewer falls with regular strength and balance exercise." source="Cochrane review, 108 trials" />
      </Sequence>
      <Sequence from={120} durationInFrames={60} name="21%">
        <Stat big={<Count to={21} />} caption="fully keep up the home exercise plan." source="Simek, McPhate and Haines, Preventive Medicine 2012" />
      </Sequence>
      <Sequence from={180} durationInFrames={60} name="Pivot">
        <Interactive.Div
          name="Playbook line"
          style={{ position: "absolute", left: 140, top: 310, fontSize: 104, fontWeight: 800, fontStretch: "106%", color: "#ffffff", lineHeight: 1.1, whiteSpace: "nowrap" }}
        >
          <Words text="The CDC wrote the playbook." start={2} stagger={3} />
        </Interactive.Div>
        <div
          style={{
            position: "absolute",
            left: 140,
            top: 450,
            display: "flex",
            gap: "0.26em",
            fontSize: 104,
            fontWeight: 800,
            fontStretch: "106%",
            color: C.onDarkMuted,
            lineHeight: 1.1,
          }}
        >
          <Words text="It lives in" start={10} stagger={3} />
          <span style={{ display: "inline-grid", overflow: "hidden", padding: "0.06em 0 0.14em", margin: "-0.06em 0 -0.14em" }}>
            <span
              style={{
                gridArea: "1 / 1",
                position: "relative",
                translate: `0 ${k(frame - 180, [18, 26], [115, 0]) - swap * 115}%`,
              }}
            >
              the clinic.
              <span
                style={{
                  position: "absolute",
                  left: 0,
                  top: "52%",
                  height: 10,
                  width: `${k(frame - 180, [26, 32], [0, 100], INOUT)}%`,
                  background: C.led,
                }}
              />
            </span>
            <span
              style={{
                gridArea: "1 / 1",
                color: C.led,
                translate: `0 ${(1 - swap) * 115}%`,
                textShadow: `0 0 40px ${C.led}88`,
              }}
            >
              your home.
            </span>
          </span>
        </div>
      </Sequence>
    </Backdrop>
  );
};
