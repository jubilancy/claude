// Feedback: draw into a small hidden canvas, copy it onto itself a little bigger
// and rotated every frame, then scale it up to the screen without smoothing.
// Each frame also brightens the colours and erases dull pixels, so shapes keep
// growing, shifting colour and dissolving. Move the pointer to move the ring.
const SCALE = 5; // buffer is 1/5 of screen size: lower = smoother, higher = chunkier
let buf, bctx;

function zoom(dw, dh, rot) {
  const w = buf.width + dw, h = buf.height + dh;
  bctx.save();
  bctx.translate(buf.width / 2, buf.height / 2);
  if (rot) bctx.rotate(rot);
  bctx.drawImage(buf, -w / 2, -h / 2, w, h);
  bctx.restore();
}

function shiftColours() {
  const img = bctx.getImageData(0, 0, buf.width, buf.height);
  const px = img.data;
  for (let i = 0; i < px.length; i += 4) {
    const r = (px[i] * 1.01) % 255, g = (px[i + 1] * 1.01) % 255, b = (px[i + 2] * 1.01) % 255;
    px[i] = r; px[i + 1] = g; px[i + 2] = b;
    const max = Math.max(r, g, b) / 255, min = Math.min(r, g, b) / 255;
    const l = (max + min) / 2;
    const s = max === min ? 0 : (max - min) / (l > 0.5 ? 2 - max - min : max + min);
    if (s <= 0.7 || l <= 0.3 || l >= 0.7) px[i + 3] = 0; // erase dull, dark or bright pixels
  }
  bctx.putImageData(img, 0, 0);
}

export default {
  readsPixels: true,

  setup({ width, height }) {
    buf = document.createElement('canvas');
    buf.width = Math.max(1, (width / SCALE) | 0);
    buf.height = Math.max(1, (height / SCALE) | 0);
    bctx = buf.getContext('2d', { willReadFrequently: true });
  },

  draw({ ctx, canvas, frame, pointer }) {
    bctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingEnabled = false;

    const t = frame / 30;
    bctx.strokeStyle = `rgb(${127 + 127 * Math.sin(t) | 0},${127 + 127 * Math.sin(t + 2.09) | 0},${127 + 127 * Math.sin(t + 4.19) | 0})`;
    bctx.beginPath();
    bctx.arc(pointer.x / SCALE, pointer.y / SCALE, 16, 0, Math.PI * 2);
    bctx.stroke();

    zoom(4, 3, Math.sin(frame / 300) / 150); // grow + twist
    zoom(-1, -1, 0);                         // pull back in slightly
    shiftColours();

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(buf, 0, 0, buf.width, buf.height, 0, 0, canvas.width, canvas.height);
  },
};
