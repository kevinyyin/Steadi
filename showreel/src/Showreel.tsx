import { Audio } from "@remotion/media";
import { TransitionSeries } from "@remotion/transitions";
import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { Flash, Leak, Shutter, Wipe } from "./Cuts";
import { Hud } from "./Hud";
import { Grain } from "./Kit";
import { Balance } from "./scenes/Balance";
import { ChairStand } from "./scenes/ChairStand";
import { Coach } from "./scenes/Coach";
import { ColdOpen } from "./scenes/ColdOpen";
import { Dashboard } from "./scenes/Dashboard";
import { DualTask } from "./scenes/DualTask";
import { Grok } from "./scenes/Grok";
import { Hardware } from "./scenes/Hardware";
import { Hook } from "./scenes/Hook";
import { Levels } from "./scenes/Levels";
import { Logo } from "./scenes/Logo";
import { Loop } from "./scenes/Loop";
import { Outro } from "./scenes/Outro";
import { Tug } from "./scenes/Tug";
import { C } from "./theme";

// Every scene is a whole number of bars (60 frames at 120 BPM). Cuts use overlays, which don't overlap scenes,
// so each scene starts on a downbeat of the soundtrack (scripts/make_music.py).
export const Showreel: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.ink }}>
    <TransitionSeries>
      <TransitionSeries.Sequence name="Cold open" durationInFrames={180}>
        <ColdOpen />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={10}>
        <Flash />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Hook" durationInFrames={240}>
        <Hook />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={24}>
        <Leak seed={3} hueShift={190} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Logo" durationInFrames={180}>
        <Logo />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence name="STEADI loop" durationInFrames={180}>
        <Loop />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence name="Hardware" durationInFrames={240}>
        <Hardware />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={20}>
        <Shutter colors={[C.ink]} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Timed Up and Go" durationInFrames={180}>
        <Tug />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={18}>
        <Wipe color={C.blue} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Dual task" durationInFrames={120}>
        <DualTask />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={20}>
        <Shutter colors={[C.ink, "#151a30"]} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Chair stand" durationInFrames={180}>
        <ChairStand />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={12}>
        <Flash />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Balance" durationInFrames={180}>
        <Balance />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={14}>
        <Shutter colors={[C.green, C.amber, C.red]} bars={9} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Levels" durationInFrames={120}>
        <Levels />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence name="Coach" durationInFrames={180}>
        <Coach />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={28} offset={-6}>
        <Leak seed={5} hueShift={200} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Dashboard" durationInFrames={240}>
        <Dashboard />
      </TransitionSeries.Sequence>
      <TransitionSeries.Overlay durationInFrames={20}>
        <Shutter colors={[C.ink]} />
      </TransitionSeries.Overlay>
      <TransitionSeries.Sequence name="Grok" durationInFrames={120}>
        <Grok />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence name="Outro" durationInFrames={180}>
        <Outro />
      </TransitionSeries.Sequence>
    </TransitionSeries>
    <Hud />
    <Grain />
    <Audio src={staticFile("music.wav")} />
  </AbsoluteFill>
);
