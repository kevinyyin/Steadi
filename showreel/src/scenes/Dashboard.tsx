import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop, Words } from "../Kit";
import { C, FONT, INOUT, k, OUT } from "../theme";

// The Steadi dashboard rebuilt in HTML with the "Simulated: Dad" history (src/checkin/seed.py), on a 3D tablet.
const SW = 1196;
const SH = 776;
const STANDS = [13, 12, 11, 10, 10, 11, 12, 13];
const EX_DAYS = [1, 1, 1, 5, 5, 5, 5, 5];
const TAB_SWITCH = 180;

const cam = (frame: number, values: number[]) =>
  interpolate(frame, [0, 36, 120, 148, 172, 198, 240], values, {
    easing: INOUT,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const Tag: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.muted }) => (
  <span style={{ fontSize: 15, fontWeight: 700, padding: "3px 8px", border: `1.5px dashed ${color}`, color }}>{children}</span>
);

const Chart: React.FC = () => {
  const frame = useCurrentFrame();
  const x = (w: number) => 60 + w * (570 / 7);
  const y = (v: number) => 330 - ((v - 8) / 6) * 300;
  const p = k(frame, [40, 110], [0, 1], INOUT);
  const len = 900;
  const d = STANDS.map((v, i) => `${i ? "L" : "M"}${x(i)} ${y(v)}`).join(" ");
  const note = k(frame, [128, 140], [0, 1]);
  return (
    <svg width={650} height={390} style={{ overflow: "visible" }}>
      {[8, 10, 12, 14].map((v) => (
        <g key={v}>
          <line x1={60} x2={630} y1={y(v)} y2={y(v)} stroke={C.line} strokeWidth={1} />
          <text x={48} y={y(v) + 5} textAnchor="end" fontSize={14} fill={C.muted}>
            {v}
          </text>
        </g>
      ))}
      <line x1={60} x2={630} y1={y(11)} y2={y(11)} stroke={C.red} strokeWidth={2} strokeDasharray="8 6" />
      <text x={66} y={y(11) + 22} fontSize={14} fontWeight={700} fill={C.red}>
        STEADI average: 11
      </text>
      <line x1={x(3)} x2={x(3)} y1={24} y2={330} stroke={C.led} strokeWidth={2} strokeDasharray="4 5" opacity={note} />
      <text x={x(3) + 8} y={40} fontSize={15} fontWeight={800} fill={C.blue} opacity={note}>
        Plan starts
      </text>
      <path d={d} fill="none" stroke={C.blue} strokeWidth={4} strokeDasharray={len} strokeDashoffset={len * (1 - p)} />
      {STANDS.map((v, i) => {
        const on = k(p, [i / 7 - 0.02, i / 7 + 0.04], [0, 1], (t) => t);
        const amber = v < 11;
        return (
          <g key={i} opacity={on}>
            <rect x={x(i) - 9} y={y(v) - 9} width={18} height={18} fill={amber ? C.amber : C.blue} stroke="#fff" strokeWidth={3} />
            <text x={x(i)} y={y(v) + (amber ? 34 : -18)} textAnchor="middle" fontSize={16} fontWeight={800} fill={C.ink}>
              {v}
            </text>
            <text x={x(i)} y={360} textAnchor="middle" fontSize={14} fill={C.muted}>
              W{i + 1}
            </text>
          </g>
        );
      })}
      <g opacity={note}>
        <rect x={x(3) - 30} y={y(10) + 46} width={200} height={30} fill={C.amber} />
        <text x={x(3) - 20} y={y(10) + 67} fontSize={16} fontWeight={800} fill={C.ink}>
          Two amber check-ins
        </text>
        <rect x={x(6) - 90} y={y(13) - 60} width={160} height={30} fill={C.green} />
        <text x={x(6) - 80} y={y(13) - 39} fontSize={16} fontWeight={800} fill="#fff">
          Back above 11
        </text>
      </g>
    </svg>
  );
};

const Home: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{ width: SW, height: SH - 70, padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ background: C.ink, color: "#fff", padding: "22px 26px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 17, color: C.onDarkMuted, fontWeight: 600 }}>Latest check-in · Simulated</div>
          <div style={{ fontSize: 38, fontWeight: 800, marginTop: 4 }}>Chair stands are back to 13.</div>
          <div style={{ fontSize: 19, color: C.onDarkMuted, marginTop: 6 }}>
            Two amber check-ins in weeks 4 and 5. Exercise went up to 5 days a week.
          </div>
        </div>
        <div style={{ background: C.green, padding: "14px 28px", fontSize: 30, fontWeight: 900, scale: String(k(frame, [20, 30], [0.6, 1])) }}>Green</div>
      </div>
      <div style={{ display: "flex", gap: 20, flex: 1 }}>
        <div style={{ background: C.paper, width: 700, padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ fontSize: 22, fontWeight: 800 }}>Chair stands, 30 seconds</div>
            <Tag>Simulated</Tag>
          </div>
          <Chart />
        </div>
        <div style={{ background: C.paper, flex: 1, padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 22, fontWeight: 800 }}>Exercise days a week</div>
            <Tag>Simulated</Tag>
          </div>
          <div style={{ position: "relative", height: 330, marginTop: 30, display: "flex", alignItems: "flex-end", gap: 12 }}>
            <div style={{ position: "absolute", left: 0, right: 0, bottom: (5 / 7) * 300, borderTop: `2px dashed ${C.muted}` }}>
              <span style={{ position: "absolute", right: 0, top: -24, fontSize: 14, fontWeight: 700, color: C.muted }}>target 5</span>
            </div>
            {EX_DAYS.map((d, i) => (
              <div key={i} style={{ flex: 1, textAlign: "center" }}>
                <div
                  style={{
                    height: (d / 7) * 300 * k(frame, [60 + i * 5, 76 + i * 5], [0, 1], OUT),
                    background: d >= 5 ? C.green : C.line,
                  }}
                />
                <div style={{ fontSize: 13, color: C.muted, marginTop: 6 }}>W{i + 1}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const ROWS = [
  ["Timed Up and Go", "10.8 s", "12 s or more flags", "−0.6 s"],
  ["30-second chair stand", "13", "below 11 flags", "+2.2"],
  ["Tandem stance", "10.0 s", "under 10 s flags", "0 s"],
  ["Dual-task cost", "16.7%", "tracked, no STEADI line", "−1.7 points"],
];

const Doctor: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{ width: SW, height: SH - 70, padding: "30px 40px", background: C.paper }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={{ fontSize: 34, fontWeight: 900 }}>For the doctor</div>
        <Tag>Simulated</Tag>
      </div>
      <div style={{ fontSize: 18, color: C.muted, marginTop: 6 }}>
        Simulated: Dad, 78, male. Fall-risk screening with the CDC&apos;s STEADI tests.
      </div>
      <div style={{ marginTop: 28 }}>
        {[["Test", "Latest", "STEADI line", "Change from baseline"], ...ROWS].map((r, i) => (
          <div
            key={i}
            style={{
              display: "grid",
              gridTemplateColumns: "1.5fr 0.8fr 1.3fr 1.2fr",
              padding: "16px 0",
              borderBottom: `1px solid ${C.line}`,
              fontSize: i ? 22 : 16,
              fontWeight: i ? 600 : 800,
              color: i ? C.ink : C.muted,
              opacity: k(frame, [TAB_SWITCH + 10 + i * 4, TAB_SWITCH + 18 + i * 4], [0, 1]),
              translate: `${k(frame, [TAB_SWITCH + 10 + i * 4, TAB_SWITCH + 24 + i * 4], [40, 0], OUT)}px 0`,
            }}
          >
            {r.map((c, j) => (
              <div key={j} style={{ fontWeight: i && j === 1 ? 900 : undefined }}>
                {c}
              </div>
            ))}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 30, opacity: k(frame, [TAB_SWITCH + 34, TAB_SWITCH + 42], [0, 1]) }}>
        <div style={{ background: C.ink, color: "#fff", padding: "14px 24px", fontSize: 20, fontWeight: 700 }}>Print summary</div>
        <div style={{ border: `2px solid ${C.ink}`, padding: "12px 22px", fontSize: 20, fontWeight: 700 }}>Copy summary</div>
      </div>
    </div>
  );
};

export const Dashboard: React.FC = () => {
  const frame = useCurrentFrame();
  const rx = cam(frame, [42, 14, 6, 0, 0, 5, 3]);
  const ry = cam(frame, [-30, -20, -8, 0, 0, 14, 8]);
  const rz = cam(frame, [8, 2, 0, 0, 0, 0, 0]);
  const s = cam(frame, [0.55, 0.84, 0.86, 1.55, 1.55, 0.84, 0.86]);
  const tx = cam(frame, [0, 30, 30, 340, 340, 0, 0]);
  const ty = cam(frame, [460, 10, 0, -200, -200, 0, -10]);
  const tab = k(frame, [TAB_SWITCH, TAB_SWITCH + 18], [0, 1], INOUT);
  const doctor = frame >= TAB_SWITCH + 6;
  const capA = k(frame, [30, 40], [0, 1]) * k(frame, [116, 126], [1, 0]);
  const capB = k(frame, [186, 196], [0, 1]);
  return (
    <Backdrop color={C.ink} grid="rgba(255,255,255,0.04)">
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 60%, ${C.blue}aa 0%, transparent 60%)` }} />
      <AbsoluteFill style={{ perspective: 2400, perspectiveOrigin: "50% 45%" }}>
        <div
          style={{
            position: "absolute",
            left: 960 - 620,
            top: 520 - 410,
            width: 1240,
            height: 820,
            transform: `translate(${tx}px, ${ty}px) rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${rz}deg) scale(${s})`,
            background: "#151a30",
            borderRadius: 40,
            padding: 22,
            boxShadow: "0 80px 120px rgba(0,0,0,0.55), inset 0 0 0 2px rgba(255,255,255,0.12)",
            fontFamily: FONT,
          }}
        >
          <div style={{ width: SW, height: SH, overflow: "hidden", borderRadius: 16, background: C.ground, color: C.ink, position: "relative" }}>
            <div style={{ height: 70, background: C.paper, borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", padding: "0 24px", gap: 22 }}>
              <div style={{ fontSize: 28, fontWeight: 800, fontStretch: "108%" }}>Steadi</div>
              <div style={{ fontSize: 20, fontWeight: 700, borderBottom: `2px solid ${C.ink}` }}>Simulated: Dad ▾</div>
              <div style={{ flex: 1 }} />
              {["Home", "Check-in", "For the doctor"].map((t) => {
                const on = t === (doctor ? "For the doctor" : "Home");
                return (
                  <div key={t} style={{ padding: "10px 18px", fontSize: 19, fontWeight: 700, background: on ? C.ink : "transparent", color: on ? "#fff" : C.ink }}>
                    {t}
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", width: SW * 2, translate: `${-tab * SW}px 0` }}>
              <Home />
              <Doctor />
            </div>
            <AbsoluteFill
              style={{
                background: `linear-gradient(${115 + ry}deg, transparent 30%, rgba(255,255,255,0.16) 45%, transparent 60%)`,
                pointerEvents: "none",
              }}
            />
          </div>
        </div>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 0, right: 0, top: 930, textAlign: "center", fontSize: 56, fontWeight: 800, color: "#fff" }}>
        <div style={{ position: "absolute", left: 0, right: 0, opacity: capA }}>
          <Words text="The family sees the trend." start={30} stagger={2} align="center" />
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, opacity: capB }}>
          <Words text="The doctor gets one page." start={186} stagger={2} align="center" />
        </div>
      </div>
    </Backdrop>
  );
};
