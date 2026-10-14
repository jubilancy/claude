// Trails: don't clear the canvas, paint a see-through black layer instead.
// Old marks fade a little each frame, which leaves a glowing tail.
export default {
  draw({ ctx, width, height, frame, pointer }) {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.05)'; // lower alpha = longer trails
    ctx.fillRect(0, 0, width, height);

    // a ring of dots orbiting the pointer; sin/cos place each dot on the circle
    const dots = 6;
    for (let i = 0; i < dots; i++) {
      const a = frame / 20 + (i * Math.PI * 2) / dots;
      const r = 40 + 30 * Math.sin(frame / 50);
      ctx.fillStyle = `hsl(${(frame * 2 + i * 60) % 360}, 90%, 60%)`;
      ctx.beginPath();
      ctx.arc(pointer.x + r * Math.cos(a), pointer.y + r * Math.sin(a), pointer.down ? 8 : 4, 0, Math.PI * 2);
      ctx.fill();
    }
  },
};
