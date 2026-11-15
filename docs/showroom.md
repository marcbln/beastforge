# Showroom and visual regression

Determinism proves the bytes are stable; the showroom proves they are still the
intended creature and that deformation has not sheared.

## Frames

For every creature the showroom renders five RGBA frames at **512 × 512**:

| View | Pose |
|------|------|
| front | rest |
| three-quarter | rest |
| side | rest |
| rear | rest |
| front | extreme-bend |

Cameras are fixed orthographic views. The extreme-bend pose rotates a declared
test joint by 90° (the second bone of the first chain, or the joint with the
most children) and skins the mesh, exposing shoulder/hip shearing.

## Rendering

- CPU-only numpy rasterizer with a z-buffer.
- One fixed key light plus ambient; two-sided Lambert shading.
- Nearest-neighbour texforge texture sampling.
- Background pixels have alpha 0; covered pixels are opaque.
- No GPU, EGL, display server, or driver dependency.

## Tolerance

Comparison uses two documented numbers:

- **Per-pixel threshold**: a pixel is *changed* when any RGBA channel differs by
  more than `8/255` (default).
- **Changed-pixel ratio**: a frame fails when more than `0.10%` of opaque pixels
  are changed.

Both are stored in the report's `tolerance` block. The comparison also reports
`max_pixel_delta` and `changed_pixel_ratio` as metrics.

Structural summaries are compared **exactly**, independently of pixels:

- joint count and names
- clip inventory (name, duration, loop, generator)
- event inventory (clip, name, time)
- skin-influence histogram and min/max weight sums
- bounds and vertex/triangle/surface counts

A structural difference is reported as the pseudo-frame `structural`.

## References

Approved references live under `showroom/reference/<creature>/`:

```text
frames/<view>__<pose>.png
structural.json
manifest.json        # tool version, frame size, tolerance, camera names
```

Compare mode renders the current build to a temporary directory and reports the
current frame paths. It exits `3` on any `fail` or `no-baseline`.

Accept mode is the only way references change:

```bash
uv run beastforge showroom --accept
uv run beastforge showroom          # must pass immediately afterwards
```

## JSON

`showroom --json` emits the `showroom.result` schema:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "ok",
  "mode": "compare",
  "tolerance": {"per_pixel_threshold": 8, "changed_pixel_ratio": 0.001},
  "creatures": [
    {
      "name": "ridge-stalker",
      "frames": [{"view": "front", "pose": "rest", "path": "...", "sha256": "..."}],
      "structural": {"joints": {"count": 24, "names": []}, "clips": [], "events": [], "skin": {}, "bounds": {}, "counts": {}},
      "comparison": {"status": "pass", "differing_frames": [], "metrics": {"max_pixel_delta": 0, "changed_pixel_ratio": 0.0}}
    }
  ]
}
```

## Workflow

1. Edit a recipe (blend, sweep modifier, skeleton, clip).
2. `uv run beastforge validate <name>` — the gate must pass.
3. `uv run beastforge showroom <name>` — inspect the differing frames.
4. If the change is intended, `uv run beastforge showroom <name> --accept`.
5. Re-run compare; it must report `pass`.
