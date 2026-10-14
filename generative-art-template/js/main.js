// Pick a sketch with ?sketch=name (default: trails), e.g. index.html?sketch=feedback
import { run } from './core.js';

const sketches = ['trails', 'feedback'];
const wanted = new URLSearchParams(location.search).get('sketch');
const name = sketches.includes(wanted) ? wanted : 'trails';

const { default: sketch } = await import(`./sketches/${name}.js`);
run(sketch, document.getElementById('canvas'));
