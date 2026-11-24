# Change Log

## Unreleased

- Capture every color observation delivered to the GCWM RoboDojo Bridge while a state-changing primitive is active, preserving Bridge receive order under `steps/NNNN/sim_NNN/` and indexing metadata in `frames.json`.
- Add `robo.sim_frames(step, sim_step=None)` for reading archived primitive-step frames as RGB NumPy arrays.
- Add the `on-sim-step` image policy and per-tool `image_return=all|final|none` overrides. Explicit `display(image)` output remains attached independently of the automatic image policy.
- Document configuration, frame reading, processing and display feedback in `doc/sim-image-frames.md`.
