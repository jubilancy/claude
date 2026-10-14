// Tiny runner: sizes the canvas, tracks the pointer, calls your sketch every frame.
//
// A sketch is an object with:
//   setup(state)  optional, runs at start and again after every resize
//   draw(state)   runs every animation frame
//
// state = { canvas, ctx, width, height, frame, pointer: { x, y, down, active } }
export function run(sketch, canvas) {
  const ctx = canvas.getContext('2d', { willReadFrequently: !!sketch.readsPixels });
  const state = {
    canvas, ctx, width: 0, height: 0, frame: 0,
    pointer: { x: 0, y: 0, down: false, active: false },
  };

  function resize() {
    state.width = canvas.width = window.innerWidth;
    state.height = canvas.height = window.innerHeight;
    state.frame = 0;
    if (!state.pointer.active) {
      state.pointer.x = state.width / 2;
      state.pointer.y = state.height / 2;
    }
    if (sketch.setup) sketch.setup(state);
  }

  // pointer events cover mouse, touch and pen with one set of handlers
  function track(e) {
    state.pointer.x = e.clientX;
    state.pointer.y = e.clientY;
    state.pointer.active = true;
  }
  canvas.addEventListener('pointermove', track);
  canvas.addEventListener('pointerdown', (e) => { track(e); state.pointer.down = true; });
  window.addEventListener('pointerup', () => { state.pointer.down = false; });

  window.addEventListener('resize', resize);
  window.addEventListener('orientationchange', resize);
  resize();

  (function loop() {
    requestAnimationFrame(loop);
    state.frame++;
    sketch.draw(state);
  })();
}
