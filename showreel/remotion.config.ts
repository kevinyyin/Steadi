import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// lightLeak() is a WebGL2 effect
Config.setChromiumOpenGlRenderer("angle");
