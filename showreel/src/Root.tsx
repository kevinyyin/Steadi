import "./index.css";
import { Composition, Folder } from "remotion";
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
import { Showreel } from "./Showreel";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="Showreel" component={Showreel} width={1920} height={1080} fps={30} durationInFrames={2520} />
      <Folder name="Scenes">
        <Composition id="ColdOpen" component={ColdOpen} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="Hook" component={Hook} width={1920} height={1080} fps={30} durationInFrames={240} />
        <Composition id="Logo" component={Logo} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="Loop" component={Loop} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="Hardware" component={Hardware} width={1920} height={1080} fps={30} durationInFrames={240} />
        <Composition id="Tug" component={Tug} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="DualTask" component={DualTask} width={1920} height={1080} fps={30} durationInFrames={120} />
        <Composition id="ChairStand" component={ChairStand} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="Balance" component={Balance} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="Levels" component={Levels} width={1920} height={1080} fps={30} durationInFrames={120} />
        <Composition id="Coach" component={Coach} width={1920} height={1080} fps={30} durationInFrames={180} />
        <Composition id="Dashboard" component={Dashboard} width={1920} height={1080} fps={30} durationInFrames={240} />
        <Composition id="Grok" component={Grok} width={1920} height={1080} fps={30} durationInFrames={120} />
        <Composition id="Outro" component={Outro} width={1920} height={1080} fps={30} durationInFrames={180} />
      </Folder>
    </>
  );
};
