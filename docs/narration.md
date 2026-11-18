# Norwegian voice-over (experiment, PROPOSED)

`moves/<id>/narration.json` holds Norwegian lines, each anchored to a trace event or a presentation segment edge.
`node scripts/video/narration.ts plan <id>` resolves the start times from the saved trace and presentation;
`node scripts/video/narration.ts build <id> [--video f.mp4]` synthesises them with local Piper (voice
`no_NO-talesyntese-medium`, fetched once into `out/voices/`, `pip install piper-tts`), fits each line before the next,
mixes, muxes into a copy of the mp4 (video stream copied, no re-render) and measures speech onsets in the result.
Report: `out/narration/<id>/narration-report.json`. Test: `tests/narration.test.ts`.
