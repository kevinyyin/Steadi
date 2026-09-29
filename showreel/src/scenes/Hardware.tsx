import React from "react";
import { AbsoluteFill, Interactive, Sequence, useCurrentFrame } from "remotion";
import { Backdrop, Words } from "../Kit";
import { C, IN, INOUT, k, OUT, pulse } from "../theme";

const W = "#ffffff";
const FILL = "rgba(255,255,255,0.07)";
const SX = 1000;
const SY = 770;
const ISO = "rotateX(60deg) rotateZ(-45deg)";

type Plate = { id: string; w: number; h: number; z0: number; z1: number; label?: [string, string]; draw: React.ReactNode };

const pins = (n: number, x0: number, y: number, step: number) =>
  Array.from({ length: n }, (_, i) => <rect key={i} x={x0 + i * step} y={y} width={10} height={10} fill={W} opacity={0.8} />);

const PLATES: Plate[] = [
  {
    id: "belt",
    w: 900,
    h: 190,
    z0: 0,
    z1: 0,
    draw: (
      <>
        <rect x={2} y={2} width={896} height={186} rx={28} fill={FILL} stroke={W} strokeWidth={3} />
        <rect x={16} y={16} width={868} height={158} rx={18} fill="none" stroke={W} strokeWidth={2} strokeDasharray="10 8" opacity={0.6} />
        {Array.from({ length: 17 }, (_, i) => (
          <line key={i} x1={60 + i * 42} x2={60 + i * 42} y1={36} y2={154} stroke={W} strokeWidth={1.5} opacity={0.18} />
        ))}
        <rect x={790} y={34} width={82} height={122} rx={10} fill="none" stroke={W} strokeWidth={4} />
        <line x1={760} x2={830} y1={95} y2={95} stroke={W} strokeWidth={4} />
      </>
    ),
  },
  {
    id: "power",
    w: 380,
    h: 210,
    z0: 16,
    z1: 120,
    label: ["USB power bank", "on the belt, all session"],
    draw: (
      <>
        <rect x={2} y={2} width={376} height={206} rx={24} fill={FILL} stroke={W} strokeWidth={3} />
        {[0, 1, 2].map((i) => (
          <rect key={i} x={60 + i * 100} y={40} width={80} height={130} rx={10} fill="none" stroke={W} strokeWidth={2} opacity={0.6} />
        ))}
        <rect x={-4} y={85} width={22} height={40} fill={W} />
      </>
    ),
  },
  {
    id: "esp32",
    w: 360,
    h: 200,
    z0: 32,
    z1: 240,
    label: ["ESP32", "Wi-Fi, UDP broadcast"],
    draw: (
      <>
        <rect x={2} y={2} width={356} height={196} rx={8} fill="rgba(255,255,255,0.1)" stroke={W} strokeWidth={3} />
        {pins(15, 22, 12, 21)}
        {pins(15, 22, 178, 21)}
        <rect x={120} y={46} width={160} height={108} rx={4} fill="rgba(58,160,255,0.25)" stroke={W} strokeWidth={3} />
        <text x={200} y={110} textAnchor="middle" fill={W} fontSize={30} fontWeight={800}>
          ESP32
        </text>
        <path d="M296 60 h40 v16 h-28 v16 h28 v16 h-28 v16 h28 v16 h-40" fill="none" stroke={W} strokeWidth={3} />
        <rect x={40} y={70} width={50} height={26} fill="none" stroke={W} strokeWidth={2} />
        <rect x={40} y={108} width={30} height={20} fill="none" stroke={W} strokeWidth={2} />
      </>
    ),
  },
  {
    id: "mpu",
    w: 200,
    h: 150,
    z0: 44,
    z1: 350,
    label: ["MPU-6050", "6-axis motion, 100 Hz"],
    draw: (
      <>
        <rect x={2} y={2} width={196} height={146} rx={8} fill="rgba(255,255,255,0.1)" stroke={W} strokeWidth={3} />
        {pins(8, 18, 10, 22)}
        <rect x={70} y={55} width={56} height={56} fill="rgba(255,255,255,0.2)" stroke={W} strokeWidth={3} />
        <line x1={98} y1={83} x2={178} y2={83} stroke="#3aa0ff" strokeWidth={5} />
        <path d="M178 83 l-14 -8 v16 z" fill="#3aa0ff" />
        <line x1={98} y1={83} x2={98} y2={30} stroke="#f2a900" strokeWidth={5} />
        <path d="M98 30 l-8 14 h16 z" fill="#f2a900" />
        <circle cx={98} cy={83} r={8} fill={W} />
      </>
    ),
  },
  {
    id: "lid",
    w: 380,
    h: 210,
    z0: 56,
    z1: 460,
    label: ["RGB LED + buzzer", "cues and sway warnings"],
    draw: null,
  },
];

const BeltStack: React.FC = () => {
  const frame = useCurrentFrame();
  const e = k(frame, [8, 46], [0, 1], INOUT);
  const out = k(frame, [110, 128], [0, 1], IN);
  const ledGlow = [15, 30, 45, 60, 75, 90, 105].reduce((m, b) => Math.max(m, pulse(frame, b, 6)), 0);
  const z = (p: Plate, i: number) => p.z0 + (p.z1 - p.z0) * e + Math.sin(frame / 18 + i) * 5 * e;
  return (
    <AbsoluteFill style={{ opacity: 1 - out, translate: `${-out * 300}px 0` }}>
      <svg width={1920} height={1080} style={{ position: "absolute" }}>
        <line x1={SX} x2={SX} y1={SY} y2={SY - 0.866 * 460 * e} stroke={W} strokeWidth={2} strokeDasharray="6 10" opacity={0.5} />
      </svg>
      {PLATES.map((p, i) => (
        <div
          key={p.id}
          style={{
            position: "absolute",
            left: SX - p.w / 2,
            top: SY - p.h / 2,
            width: p.w,
            height: p.h,
            transform: `${ISO} translateZ(${z(p, i)}px)`,
            opacity: k(frame, [i * 3, i * 3 + 8], [0, 1]),
          }}
        >
          <svg width={p.w} height={p.h} style={{ overflow: "visible" }}>
            {p.id === "lid" ? (
              <>
                <rect x={2} y={2} width={376} height={206} rx={24} fill={FILL} stroke={W} strokeWidth={3} />
                <circle cx={90} cy={105} r={22 + ledGlow * 30} fill="#3aa0ff" opacity={0.25 * ledGlow} />
                <circle cx={90} cy={105} r={20} fill="#3aa0ff" stroke={W} strokeWidth={3} />
                {[18, 34, 50].map((r) => (
                  <circle key={r} cx={280} cy={105} r={r} fill="none" stroke={W} strokeWidth={2.5} opacity={0.8} />
                ))}
              </>
            ) : (
              p.draw
            )}
          </svg>
        </div>
      ))}
      {PLATES.filter((p) => p.label).map((p, i) => {
        const y = SY - 0.866 * p.z1;
        const fp = (p.w + p.h) / 2.83;
        const s = 45 + (3 - i) * 8;
        const draw = k(frame, [s, s + 12], [0, 1], OUT);
        return (
          <React.Fragment key={p.id}>
            <svg width={1920} height={1080} style={{ position: "absolute" }}>
              <circle cx={SX + fp * 0.55} cy={y} r={7 * draw} fill={W} />
              <line x1={SX + fp * 0.55} x2={SX + fp * 0.55 + (1410 - SX - fp * 0.55) * draw} y1={y} y2={y} stroke={W} strokeWidth={2} />
            </svg>
            <div style={{ position: "absolute", left: 1436, top: y - 40, opacity: k(frame, [s + 6, s + 14], [0, 1]), translate: `${k(frame, [s + 6, s + 18], [30, 0])}px 0` }}>
              <div style={{ fontSize: 44, fontWeight: 800, color: W, lineHeight: 1.05 }}>{p.label![0]}</div>
              <div style={{ fontSize: 28, fontWeight: 600, color: C.blueSoft }}>{p.label![1]}</div>
            </div>
          </React.Fragment>
        );
      })}
      <Interactive.Div
        name="Belt title"
        style={{ position: "absolute", left: 140, top: 130, color: "#ffffff" }}
      >
        <Words text="The belt." start={4} style={{ fontSize: 140, fontWeight: 900, fontStretch: "112%", lineHeight: 1 }} />
        <Words text="Worn at the lower back." start={12} style={{ fontSize: 52, fontWeight: 600, color: "#b3c1f4", marginTop: 18 }} />
      </Interactive.Div>
    </AbsoluteFill>
  );
};

const PRESSES = [17, 32, 47];

const BaseStation: React.FC = () => {
  const frame = useCurrentFrame();
  const inn = k(frame, [0, 18], [0, 1], OUT);
  const out = k(frame, [54, 64], [0, 1], IN);
  const press = PRESSES.reduce((m, p) => Math.max(m, pulse(frame, p, 4)), 0);
  return (
    <AbsoluteFill style={{ opacity: 1 - out }}>
      <Interactive.Div name="Button title" style={{ position: "absolute", left: 140, top: 330, color: "#ffffff" }}>
        <Words text="One button." start={2} style={{ fontSize: 128, fontWeight: 900, fontStretch: "110%", lineHeight: 1 }} />
        <Words text={"The base station beeps\nevery cue."} start={10} style={{ fontSize: 60, fontWeight: 600, color: "#b3c1f4", marginTop: 26, lineHeight: 1.15 }} />
      </Interactive.Div>
      <svg width={1920} height={1080} style={{ position: "absolute", opacity: inn, translate: `0 ${(1 - inn) * 80}px` }}>
        <rect x={1100} y={390} width={660} height={380} rx={30} fill={FILL} stroke={W} strokeWidth={4} />
        <circle cx={1360} cy={580} r={140} fill="none" stroke={W} strokeWidth={3} opacity={0.5} />
        <circle cx={1360} cy={580} r={128 + press * 26} fill="#3aa0ff" opacity={press * 0.35} />
        <circle cx={1360} cy={580 + press * 8} r={112 * (1 - press * 0.06)} fill={W} />
        <circle cx={1360} cy={580 + press * 8} r={80 * (1 - press * 0.06)} fill="none" stroke={C.blue} strokeWidth={3} opacity={0.3} />
        <circle cx={1170} cy={450} r={16} fill={press > 0.2 ? "#3aa0ff" : "rgba(255,255,255,0.3)"} stroke={W} strokeWidth={3} />
        <circle cx={1170} cy={450} r={16 + press * 22} fill="#3aa0ff" opacity={press * 0.4} />
        {Array.from({ length: 16 }, (_, i) => (
          <circle key={i} cx={1600 + (i % 4) * 30} cy={535 + Math.floor(i / 4) * 30} r={7} fill={W} opacity={0.75} />
        ))}
        {PRESSES.map((p) =>
          [0, 6].map((d) => {
            const t = frame - p - d;
            if (t < 0 || t > 22) return null;
            const r = 50 + t * 9;
            return (
              <path
                key={`${p}-${d}`}
                d={`M ${1705 + r * Math.cos(-0.8)} ${580 + r * Math.sin(-0.8)} A ${r} ${r} 0 0 1 ${1705 + r * Math.cos(0.8)} ${580 + r * Math.sin(0.8)}`}
                fill="none"
                stroke={W}
                strokeWidth={4}
                opacity={1 - t / 22}
              />
            );
          }),
        )}
        <text x={1100} y={830} fill={C.blueSoft} fontSize={32} fontWeight={600}>
          Arduino base station: button, RGB LED, buzzer
        </text>
      </svg>
    </AbsoluteFill>
  );
};

const SourceIcon: React.FC<{ kind: number }> = ({ kind }) =>
  kind === 0 ? (
    <svg width={220} height={140}>
      <rect x={4} y={56} width={212} height={40} rx={18} fill="none" stroke={W} strokeWidth={4} />
      <rect x={70} y={34} width={80} height={84} rx={10} fill={C.blue} stroke={W} strokeWidth={4} />
      <circle cx={110} cy={60} r={8} fill="#3aa0ff" />
    </svg>
  ) : kind === 1 ? (
    <svg width={220} height={140}>
      <rect x={70} y={4} width={80} height={132} rx={14} fill="none" stroke={W} strokeWidth={4} />
      <path d="M84 80 q13 -30 26 0 t26 0" fill="none" stroke="#3aa0ff" strokeWidth={4} />
    </svg>
  ) : (
    <svg width={220} height={140}>
      <rect x={40} y={14} width={140} height={112} fill="none" stroke={W} strokeWidth={4} strokeDasharray="10 8" />
      <path d="M52 76 q14 -40 28 0 t28 0 t28 0 t28 0" fill="none" stroke="#3aa0ff" strokeWidth={4} />
    </svg>
  );

const Network: React.FC = () => {
  const frame = useCurrentFrame();
  const kind = frame < 22 ? 0 : frame < 38 ? 1 : 2;
  const flip = [22, 38].reduce((m, s) => Math.max(m, frame >= s && frame < s + 8 ? 1 - (frame - s) / 8 : 0), 0);
  const draw1 = k(frame, [6, 18], [0, 1], INOUT);
  const draw2 = k(frame, [12, 24], [0, 1], INOUT);
  const links: [number, number, number][] = [
    [560, 820, draw1],
    [1100, 1360, draw2],
  ];
  const node = (x: number, s: number, icon: React.ReactNode, name: string) => (
    <div
      style={{
        position: "absolute",
        left: x - 200,
        width: 400,
        whiteSpace: "nowrap",
        top: 520,
        textAlign: "center",
        opacity: k(frame, [s, s + 8], [0, 1]),
        translate: `0 ${k(frame, [s, s + 14], [30, 0])}px`,
      }}
    >
      <div style={{ height: 150, display: "flex", justifyContent: "center", alignItems: "center" }}>{icon}</div>
      <div style={{ fontSize: 40, fontWeight: 800, color: W, marginTop: 20 }}>{name}</div>
    </div>
  );
  return (
    <AbsoluteFill>
      <Interactive.Div name="Network title" style={{ position: "absolute", left: 140, top: 140, color: "#ffffff" }}>
        <Words text="Belt, phone, or simulator." start={2} stagger={2} style={{ fontSize: 100, fontWeight: 900, fontStretch: "108%", lineHeight: 1 }} />
        <Words text="Same interface. Works offline." start={10} stagger={2} style={{ fontSize: 52, fontWeight: 600, color: "#b3c1f4", marginTop: 20 }} />
      </Interactive.Div>
      <AbsoluteFill style={{ scale: "1.18", transformOrigin: "960px 640px" }}>
      <svg width={1920} height={1080} style={{ position: "absolute" }}>
        {links.map(([a, b, d], i) => (
          <g key={i}>
            <line x1={a} x2={a + (b - a) * d} y1={595} y2={595} stroke={W} strokeWidth={3} />
            {d >= 1
              ? [0, 1, 2].map((j) => {
                  const u = ((frame * 0.035 + j / 3) % 1 + 1) % 1;
                  return <rect key={j} x={a + (b - a) * u - 7} y={588} width={14} height={14} fill="#3aa0ff" />;
                })
              : null}
          </g>
        ))}
        <text x={690} y={560} textAnchor="middle" fill={C.blueSoft} fontSize={30} fontWeight={700} opacity={draw1}>
          motion, 100 Hz
        </text>
        <text x={1230} y={560} textAnchor="middle" fill={C.blueSoft} fontSize={30} fontWeight={700} opacity={draw2}>
          WebSocket
        </text>
      </svg>
      {node(
        410,
        2,
        <div style={{ transform: `perspective(600px) rotateX(${flip * 90}deg)` }}>
          <SourceIcon kind={kind} />
        </div>,
        ["Belt", "Phone", "Simulator"][kind],
      )}
      {node(
        960,
        8,
        <svg width={240} height={150}>
          <rect x={30} y={10} width={180} height={110} fill="none" stroke={W} strokeWidth={4} />
          <path d="M10 138 h220 l-14 -16 h-192 z" fill={W} />
          <path d="M52 90 l30 -30 l24 18 l40 -44 l30 22" fill="none" stroke="#3aa0ff" strokeWidth={4} />
        </svg>,
        "Laptop",
      )}
      {node(
        1510,
        14,
        <svg width={240} height={150}>
          <rect x={20} y={6} width={200} height={138} rx={12} fill="none" stroke={W} strokeWidth={4} />
          {[0, 1, 2, 3, 4].map((i) => (
            <rect key={i} x={50 + i * 30} y={112 - [30, 40, 26, 60, 72][i]} width={18} height={[30, 40, 26, 60, 72][i]} fill={i > 2 ? "#3aa0ff" : W} />
          ))}
        </svg>,
        "Family dashboard",
      )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const Hardware: React.FC = () => (
  <Backdrop color={C.blue} grid="rgba(255,255,255,0.07)" major="rgba(255,255,255,0.1)" size={40} drift={0.3}>
    <Sequence  durationInFrames={130} name="Belt stack">
      <BeltStack />
    </Sequence>
    <Sequence from={118} durationInFrames={64} name="Base station">
      <BaseStation />
    </Sequence>
    <Sequence from={178} durationInFrames={62} name="Network">
      <Network />
    </Sequence>
  </Backdrop>
);
