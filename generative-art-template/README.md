# Generative art template

A dependency-free starting point for canvas art: plain HTML, CSS and JavaScript. No build step, no framework, no libraries.

## Use it

1. Click **Use this template** on GitHub (the repo must have *Template repository* ticked under Settings → General).
2. Turn on hosting: Settings → Pages → deploy from your branch. Your art gets a public URL.
3. Edit a file in `js/sketches/` in GitHub's web editor (press `.`) or in a Claude Code session, commit, refresh the page.

Open `index.html?sketch=trails` or `index.html?sketch=feedback` to switch sketches. (`js/main.js` uses ES modules, so open it through a URL rather than as a `file://` page.)

## Make your own sketch

Copy `js/sketches/trails.js` to `js/sketches/mine.js`, add `'mine'` to the list in `js/main.js`, and edit. A sketch is:

```js
export default {
  setup({ width, height }) {},          // optional; runs at start and on resize
  draw({ ctx, width, height, frame, pointer }) {}, // runs every frame
};
```

`pointer` has `x`, `y`, `down` (mouse button or finger held) and `active`. It works for mouse, touch and pen.

## Techniques used here

| Technique | Where | How it works |
| :--- | :--- | :--- |
| Trails | `trails.js` | Paint `rgba(0,0,0,0.05)` over the canvas instead of clearing it. Old marks fade slowly. |
| Orbits and waves | `trails.js` | `Math.sin` and `Math.cos` turn a growing frame counter into circular or oscillating motion. |
| Feedback loop | `feedback.js` | Draw the canvas onto itself slightly bigger and rotated each frame. Small changes compound into patterns. |
| Chunky pixels | `feedback.js` | Render small, then scale up with `imageSmoothingEnabled = false`. Also makes per-pixel work cheap. |
| Per-pixel rules | `feedback.js` | `getImageData`, change each pixel, `putImageData`. |

## Ideas to try

- Change the numbers: trail alpha, `SCALE`, the `1.01` colour multiplier, the zoom amounts. Tiny changes alter the whole look.
- Swap the ring for a spiral, a polygon, or text.
- Combine a trail layer with a feedback layer.
- Keep a `frame` counter and drive everything from `Math.sin(frame / n)` so motion loops smoothly.
