# Steadi showreel

An 84-second motion reel of Steadi, made in [Remotion](https://www.remotion.dev). 1920×1080, 30 fps, 120 BPM: every scene is a whole number of bars, so cuts land on the downbeat.

```bash
npm i
npm run dev                                    # Remotion Studio; each scene is also its own composition under "Scenes"
npx remotion render Showreel out/steadi-showreel.mp4 --codec=h264 --crf=18
uv run --no-project --with numpy --with scipy python scripts/make_music.py   # regenerate public/music.wav
```

- `src/theme.ts`: Steadi's colour tokens and the vendored variable Archivo font (width and weight axes are animated).
- `src/scenes/`: one file per scene. `src/Showreel.tsx` puts them in order with cut overlays from `src/Cuts.tsx`.
- `scripts/make_music.py`: the soundtrack is synthesized, including the base-station beeps placed on the frames where they happen on screen. If you retime a scene, update the frames there too.
- Every product value shown is from the "Simulated: Dad" history and is labelled Simulated.
