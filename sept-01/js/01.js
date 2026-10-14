// Feedback-loop rainbow ring, rendered on a 1/5-scale buffer and scaled up
// without smoothing. Each frame: stamp a ring, re-draw the buffer onto itself
// (slightly zoomed + rotated), shift colours, then erase dull/dark/bright pixels.
(function () {
  var SCALE = 5;
  var visible = document.getElementById('canvas');
  var vctx = visible.getContext('2d');
  var buf, bctx, frames = 0, raf = 0;

  function smooth(ctx, on) {
    ctx.imageSmoothingEnabled = on;
    ctx.webkitImageSmoothingEnabled = on;
    ctx.mozImageSmoothingEnabled = on;
  }

  function rainbow(t, phase) {
    var r = 127 + 127 * Math.sin(t);
    var g = 127 + 127 * Math.sin(t + phase * 2 * Math.PI / 3);
    var b = 127 + 127 * Math.sin(t + phase * 4 * Math.PI / 3);
    return 'rgb(' + (r | 0) + ',' + (g | 0) + ',' + (b | 0) + ')';
  }

  // Redraw the buffer onto itself, grown by (dw,dh) px and rotated by `rot`.
  function feedback(dw, dh, rot) {
    var w = buf.width + dw, h = buf.height + dh;
    bctx.save();
    bctx.translate(buf.width / 2, buf.height / 2);
    if (rot) bctx.rotate(rot);
    bctx.drawImage(buf, -w / 2, -h / 2, w, h);
    bctx.restore();
  }

  // Brighten each channel by 1%, wrapping at 255, then make a pixel
  // transparent unless its saturation > 0.7 and lightness is in (0.3, 0.7).
  function shiftColours() {
    var img = bctx.getImageData(0, 0, buf.width, buf.height);
    var px = img.data;
    for (var i = 0; i < px.length; i += 4) {
      var r = (px[i] * 1.01) % 255;
      var g = (px[i + 1] * 1.01) % 255;
      var b = (px[i + 2] * 1.01) % 255;
      px[i] = r; px[i + 1] = g; px[i + 2] = b;

      var max = Math.max(r, g, b) / 255, min = Math.min(r, g, b) / 255;
      var l = (max + min) / 2;
      var s = max === min ? 0 : (max - min) / (l > 0.5 ? 2 - max - min : max + min);
      if (s <= 0.7 || l <= 0.3 || l >= 0.7) px[i + 3] = 0;
    }
    bctx.putImageData(img, 0, 0);
  }

  function frame() {
    raf = requestAnimationFrame(frame);
    frames++;

    smooth(bctx, true);
    smooth(vctx, false);

    bctx.strokeStyle = rainbow(frames / 30, Math.sin(frames / 301));
    bctx.beginPath();
    bctx.arc(buf.width / 2, buf.height / 2, 16, 0, Math.PI * 2);
    bctx.stroke();

    feedback(4, 3, Math.sin(frames / 300) / 150);
    feedback(-1, -1, 0);
    shiftColours();

    vctx.clearRect(0, 0, visible.width, visible.height);
    vctx.drawImage(buf, 0, 0, buf.width, buf.height, 0, 0, visible.width, visible.height);
  }

  function setup() {
    cancelAnimationFrame(raf);
    visible.width = window.innerWidth;
    visible.height = window.innerHeight;
    buf = document.createElement('canvas');
    buf.width = Math.max(1, (window.innerWidth / SCALE) | 0);
    buf.height = Math.max(1, (window.innerHeight / SCALE) | 0);
    bctx = buf.getContext('2d', { willReadFrequently: true });
    frames = 0;
    frame();
  }

  window.addEventListener('resize', setup);
  window.addEventListener('orientationchange', setup);
  setup();
})();
