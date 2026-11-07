// Proves the brief against the exported file itself, not the Blender scene.  Run: node verify_glb.js
const fs = require('fs'), path = require('path');
const core = fs.readFileSync(path.join(__dirname, 'glb-core.js'), 'utf8');
const { parseGLB, makeClip, sampleChannel } = new Function(core + ';return {parseGLB,makeClip,sampleChannel}')();
const file = path.join(__dirname, '..', 'loop.glb');
const buf = fs.readFileSync(file);
const glb = parseGLB(new Uint8Array(buf));
const clip = makeClip(glb, 0);
const nodes = glb.json.nodes;
let fails = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? '  ' + detail : '')); if (!ok) fails++; };

check('GLB under 1 MB', buf.length < 1e6, (buf.length / 1024).toFixed(1) + ' KB');
check('Loop lasts 5:00', Math.abs(clip.duration - 300) < 1e-3, clip.duration.toFixed(3) + ' s');
check('One animation holds every channel', glb.json.animations.length === 1, clip.channels.length + ' channels');

const ch = (node, p) => clip.channels.find(c => nodes[c.node].name === node && c.path === p);
const at = (c, t) => Array.from(sampleChannel(c, t, new Float32Array(c.size)));
const dist = (a, b) => Math.sqrt(a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0));

// at least three keyframes that actually change position, rotation and scale
for (const p of ['translation', 'rotation', 'scale']) {
  const c = ch('Robot_Head', p), seen = new Set();
  for (let i = 0; i < c.times.length; i++) seen.add(at(c, c.times[i]).map(v => v.toFixed(3)).join());
  check('Root ' + p + ' keys', c.times.length >= 3 && seen.size >= 3, c.times.length + ' keys, ' + seen.size + ' distinct values');
}

// seamless: last pose equals first pose and motion is at rest either side of the seam
const h = 1 / 240;
let seam = 0, seamV = 0;
for (const c of clip.channels) {
  seam = Math.max(seam, dist(at(c, 0), at(c, 300)));
  seamV = Math.max(seamV, dist(at(c, h), at(c, 0)) / h, dist(at(c, 300), at(c, 300 - h)) / h);
}
check('No jump at the seam (pose)', seam < 1e-4, 'largest difference ' + seam.toExponential(2));
check('No jump at the seam (velocity)', seamV < .05, 'largest speed next to the seam ' + seamV.toFixed(4) + ' units/s');

// eased: speed is never flat, it rises from zero and falls back to zero in every move
for (const p of ['translation', 'rotation', 'scale']) {
  const c = ch('Robot_Head', p);
  let moving = 0, eased = 0, peakRatio = 0;
  for (let i = 0; i < c.times.length - 1; i++) {
    const a = c.times[i], b = c.times[i + 1], d = b - a;
    if (dist(at(c, a), at(c, b)) < .01) continue;       // a near-still hold
    const eps = d / 2000, speed = u => dist(at(c, a + u * d + eps), at(c, a + u * d - eps)) / (2 * eps);
    const start = speed(.02), mid = speed(.5), end = speed(.98);
    moving++;
    if (start < mid * .25 && end < mid * .25) eased++;
    peakRatio = Math.max(peakRatio, mid / Math.max(start, 1e-6));
  }
  const spin = p === 'rotation';   // keys inside a spin carry its speed on purpose, so only the whole spin eases
  check('Root ' + p + ' eases in and out', spin ? eased / moving > .6 : eased === moving, eased + ' of ' + moving + ' moves');
}

// a spin eases as a whole
{
  const c = ch('Robot_Head', 'rotation'), ang = t => { const q = at(c, t); return Math.acos(Math.min(1, Math.abs(q[3]))) * 2; };
  let flat = 0, total = 0, last = null;
  for (let t = 0.05; t < 300; t += .1) {
    const v = ang(t + .05) - ang(t - .05);
    if (last !== null) { total++; if (Math.abs(Math.abs(v) - Math.abs(last)) < 1e-5 && Math.abs(v) > 1e-3) flat++; }
    last = v;
  }
  check('Never a run of constant rotation speed', flat / total < .02, (100 * flat / total).toFixed(2) + '% of samples');
}

// rotation keys must stay on one continuous path, or a cubic spline snaps through zero
{
  let breaks = 0;
  for (const c of clip.channels.filter(c => c.path === 'rotation')) {
    for (let i = 1; i < c.times.length; i++) {
      const p = at(c, c.times[i - 1]), q = at(c, c.times[i]);
      if (p.reduce((s, x, k) => s + x * q[k], 0) < 0) breaks++;
    }
  }
  check('Rotation keys are sign continuous', breaks === 0, breaks + ' breaks');
}

// the GLB must match what Blender shows. Blender axes become glTF axes as (x, z, -y)
const ref = JSON.parse(fs.readFileSync(path.join(__dirname, 'blender_samples.json')));
const worst = { translation: 0, rotation: 0, scale: 0 };
for (const c of clip.channels) {
  const name = nodes[c.node].name;
  for (const s of ref[name]) {
    const v = at(c, s.f / ref.fps);
    let want;
    if (c.path === 'translation') want = [s.loc[0], s.loc[2], -s.loc[1]];
    else if (c.path === 'scale') want = [s.scl[0], s.scl[2], s.scl[1]];
    else {
      want = [s.rot[1], s.rot[3], -s.rot[2], s.rot[0]];
      if (want.reduce((a, x, i) => a + x * v[i], 0) < 0) want = want.map(x => -x);
    }
    worst[c.path] = Math.max(worst[c.path], dist(v, want));
  }
}
check('GLB matches Blender at ' + ref.Robot_Head.length + ' sampled frames',
  worst.translation < 2e-3 && worst.rotation < 2e-3 && worst.scale < 2e-3,
  'worst error ' + JSON.stringify(Object.fromEntries(Object.entries(worst).map(([k, v]) => [k, +v.toExponential(2)]))));

console.log(fails ? '\n' + fails + ' check(s) FAILED' : '\nAll checks passed');
process.exit(fails ? 1 : 0);
