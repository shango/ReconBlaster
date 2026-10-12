# Changelog

Versions follow [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH`.
The version lives in `reconblaster/__init__.py` as `__version__` and is
shown in the window title.

## 3.0.2

- **View transform** checkbox next to the passes turns the viewport's colour
  view transform on or off for the Material pass. The playblast colour
  management prefs are put back after the pass.
- After **Process** the scene is left as it was before the tool ran: the
  lighting rig and its `rbLightRig` namespace are deleted, and the current
  frame is put back. Add the rig again before the next run.

## 3.0.1

- The lighting rig scene `reconblaster/lighting_rig.ma` now ships with the
  tool, so **Add lighting rig** imports the `lights` group (ambient, key,
  fill/bounce and point lights) instead of reporting the scene missing.

## 3.0.0

- Renamed from Playblast Frames to **ReconBlaster**. The package is now
  `reconblaster` (`import reconblaster; reconblaster.show()`), the shelf
  button is **ReconBlaster** and the zip is `reconblaster_3.0.0.zip`.
- Queue files are saved as `<scene>_reconblaster.json`. A shot that only has
  an old `<scene>_playblast_cams.json` still loads from it, and the next
  change is saved under the new name.
- Settings are stored under `reconBlaster*` optionVars. The old
  `playblastFrames*` ones are copied across the first time the tool opens.
- The lighting rig is imported under the `rbLightRig` namespace instead of
  `pbfLightRig`, and lives at `reconblaster/lighting_rig.ma`.

## 2.2.0

- New **Checker** pass (`checker`): the character in a lambert with a checker
  texture, to show its UVs.
- The Shaded pass is a plain grey lambert again instead of a blinn.
- Every pass is lit by all the scene's lights, with shadows and ambient
  occlusion on. Every light is made to cast shadows for the capture, and put
  back afterwards. Scenes with no lights fall back to Maya's default light.
- Wireframe lines are drawn smoothed, and anti-aliasing stays at 16x.
- **Select** button next to the character geometry selects it in Maya.
- **Add lighting rig** imports the lighting rig scene
  (`playblast_frames/lighting_rig.ma`) under the `pbfLightRig` namespace and
  selects it so you can adjust it. If it is already in the scene, it is just
  selected.

## 2.1.0

- New **Plate** pass (`plate`): the camera's image plane on its own, with the
  character hidden.
- The Shaded pass is now just the grey lambert, with no wireframe drawn over
  it, and is written as `shaded` instead of `wireOnShaded`.
- The Shaded pass uses a grey blinn with its specular turned off instead of
  a lambert.
- Each camera now writes up to four images: Plate, Wireframe, Shaded and
  Material.

## 2.0.3

- The Shaded (`wireOnShaded`) pass puts a plain grey lambert on the character
  instead of Maya's viewport default material.

## 2.0.2

- The queue's Frame column is wide enough for frame numbers like 1001; it
  was sized to the header text and cut four-digit frames off.

## 2.0.1

- Fixed **Add** (and double-click, Add all, Enter) doing nothing in 2.0.0: the
  queue table was handed a list item, so each add left a blank row with no
  camera or frame and raised an error in the Script Editor.

## 2.0.0

- Each queued camera has its own frame. The queue is a Camera | Frame table;
  cameras are added at the current frame, and **Set to current frame** stamps
  the time slider's frame onto the selected rows.
- Captures show only the character geometry, picked with **Set from
  selection**, plus the camera's image plane.
- Passes are now Wireframe (`wire`), Shaded (`wireOnShaded`) and Material
  (`material`), chosen with checkboxes; at least one stays on. The Wireframe
  pass puts a useBackground shader on the character so back-facing wires are
  hidden and the plate shows through. The old scene-wide `shaded` pass is
  replaced by the character-only Material pass.
- The wireframe colour applies to the character only.
- The queue file is now an object holding the character and each camera's
  frame. 1.x list files still load, at the current frame.
- Removed **Capture all cameras in scene**, since every camera needs a frame.
- The version is shown in the bottom-right corner of the window as well as the
  title bar.

## 1.1.0

- Burn-in on every image: rig name, camera and pass, along the bottom left.
  The rig name is the camera's namespace, falling back to the scene filename.
  Drawn with Qt, so there is nothing extra to install.
- Captures are 4K. Width is pinned to 3840 and the height follows the render
  globals' aspect ratio, so framing still matches the shot.
- The camera queue is saved to a JSON file beside the scene instead of a Maya
  optionVar, so the chosen cameras travel with the shot and survive a prefs
  reset. Loading no longer writes back, so opening the tool before a reference
  has loaded cannot wipe the saved queue.
- Wireframe colour is a single user-picked colour. The per-object contrasting
  colour option has been removed.
- Documented that anti-aliasing was already at Viewport 2.0's maximum
  (`multiSampleCount` 16 plus `lineAAEnable`). No behaviour change.

## 1.0.0

First release. Queue cameras with fuzzy search, capture a shaded and a
wire-on-shaded pass per camera at the current frame, at the render globals'
resolution.
