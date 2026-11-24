# Simulation Image Frames for Agent Developers

This note describes the GCWM Agent side of RoboDojo image capture. The integration subscribes to image observations as the Bridge receives them and archives each received image frame in order. The simulator client and the `Jasper/RoboDojo` checkout are not modified.

## Returned images

The deployment setting `images` controls automatic image feedback:

| Value | Tool result |
| --- | --- |
| `on-motion` | Final camera images after a tool call that moved the robot. |
| `on-primitive` | Final camera images after each state-changing primitive in the call. |
| `on-sim-step` | Every Bridge image frame received while each state-changing primitive ran, in receive order, including the last received frame. |
| `on-demand` | Only images requested with `robo.show(camera)`, plus images passed to `display()`. |
| `none` | No automatic camera images; images passed to `display()` are still attached. |

The `python` and `run_program` tool schemas accept `image_return` to override the deployment setting for one call:

| `image_return` | Behavior |
| --- | --- |
| `all` | Return all archived Bridge frames for state-changing primitives executed by this call. |
| `final` | Return the final observation images after movement. |
| `none` | Do not automatically attach simulator images. Explicit `display(image)` output remains attached. |

Omit `image_return` to use the deployment setting. Frame archival runs independently of these settings and does not require the Agent to read or return the frames.

## Read frames in policy code

`robo.sim_frames(step=-1, sim_step=None)` returns frames for one primitive step. `step` is the recorded primitive step, with `-1` selecting the latest. `sim_step` optionally selects one one-based frame in Bridge receive order. Each returned dictionary contains:

- `step`: primitive step number.
- `sim_step`: one-based frame number within that primitive step.
- `seq`: monotonically increasing Bridge receive sequence.
- `source_step`: environment step value reported with that Bridge observation, when available.
- `tool`: state-changing tool that was active when the frame arrived.
- `images`: camera name to RGB `numpy.ndarray` (`uint8`, height x width x 3).

For example, this cells-arm call inspects every captured head-camera frame and returns the last one with a simple contact sheet:

```python
frames = robo.sim_frames(step=1)
head_frames = [frame["images"]["cam_head"] for frame in frames if "cam_head" in frame["images"]]
print("received frames:", len(head_frames))

if head_frames:
    from PIL import Image, ImageDraw

    thumb_width, thumb_height = 240, 180
    sheet = Image.new("RGB", (thumb_width * len(head_frames), thumb_height))
    for index, array in enumerate(head_frames):
        thumb = Image.fromarray(array).resize((thumb_width, thumb_height))
        sheet.paste(thumb, (index * thumb_width, 0))
        ImageDraw.Draw(sheet).text((index * thumb_width + 4, 4), str(index + 1), fill="red")
    display(sheet)
```

For the `program` arm, use the same API inside `run(robo)`. A tool call can suppress raw frame attachments while still allowing code to inspect them and return a processed image:

```json
{"code": "...", "image_return": "none"}
```

Call `display(image)` once per processed image to attach it to the tool result and therefore the model context. `display()` accepts a NumPy array, PIL image or PNG bytes. The original raw Bridge frames remain available in the archive regardless of whether they are displayed.

## Archive layout

Under an episode result directory, captured observations are stored as:

```text
steps/
  0000/                         # initial observation
    cam_head.png
    ...
    frames.json
  0001/                         # first state-changing primitive result
    sim_001/                    # first Bridge frame received during the primitive
      cam_head.png
      cam_left_wrist.png
      cam_right_wrist.png
    sim_002/
      ...
    final/                      # final observation recorded for this primitive
      cam_head.png
      ...
    frames.json
```

`sim_NNN` directories are assigned sequentially in Bridge receive order. `frames.json` records the Bridge `seq`, source environment `sim_step`, active tool and camera names for each archived frame. `final/` is the primitive's final observation artifact used by existing `robo.image()`, `robo.show()` and `image_return=final` paths. Initial observation images remain directly in `steps/0000/`.

The archive contains frames the GCWM Bridge received. It does not infer whether the simulator emitted additional frames that never reached the client. Camera images in the archive are raw captured observations; no resizing, deduplication or compositing is applied.
