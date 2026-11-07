/* Minimal GLB reader and glTF animation sampler. No libraries. Shared by the page and the tests. */
function parseGLB(bytes) {
  var view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (view.getUint32(0, true) !== 0x46546c67) throw new Error('Not a GLB file');
  var jsonLen = view.getUint32(12, true);
  var text = '';
  for (var i = 0; i < jsonLen; i++) text += String.fromCharCode(bytes[20 + i]);
  var json = JSON.parse(text);
  var binStart = 20 + jsonLen + 8;
  var TYPES = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
  var CTOR = { 5121: Uint8Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
  function accessor(i) {
    var a = json.accessors[i], bv = json.bufferViews[a.bufferView];
    var Ctor = CTOR[a.componentType], n = a.count * TYPES[a.type];
    var start = binStart + (bv.byteOffset || 0) + (a.byteOffset || 0);
    var end = start + n * Ctor.BYTES_PER_ELEMENT;
    return new Ctor(bytes.buffer.slice(bytes.byteOffset + start, bytes.byteOffset + end));
  }
  return { json: json, accessor: accessor };
}

/* One clip: every channel of animation `index`, with its keys read into typed arrays. */
function makeClip(glb, index) {
  var anim = glb.json.animations[index], duration = 0;
  var channels = anim.channels.map(function (c) {
    var s = anim.samplers[c.sampler], times = glb.accessor(s.input), values = glb.accessor(s.output);
    duration = Math.max(duration, times[times.length - 1]);
    return {
      node: c.target.node, path: c.target.path, interpolation: s.interpolation || 'LINEAR',
      times: times, values: values, size: c.target.path === 'rotation' ? 4 : 3, last: 0
    };
  });
  return { channels: channels, duration: duration, name: anim.name };
}

/* Evaluate a channel at time t, writing the result into out. CUBICSPLINE follows the glTF 2.0 spec. */
function sampleChannel(ch, t, out) {
  var T = ch.times, n = T.length, size = ch.size, V = ch.values, cubic = ch.interpolation === 'CUBICSPLINE';
  var stride = cubic ? size * 3 : size, base = cubic ? size : 0, i, c;
  if (t <= T[0]) { for (c = 0; c < size; c++) out[c] = V[base + c]; return out; }
  if (t >= T[n - 1]) { for (c = 0; c < size; c++) out[c] = V[(n - 1) * stride + base + c]; return out; }
  i = ch.last;                                   // playback is mostly forward, so start from the last key
  if (t < T[i] || t >= T[i + 1]) {
    var lo = 0, hi = n - 1;
    while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (T[mid] <= t) lo = mid; else hi = mid; }
    i = ch.last = lo;
  }
  var dt = T[i + 1] - T[i], u = (t - T[i]) / dt;
  if (ch.interpolation === 'STEP') {
    for (c = 0; c < size; c++) out[c] = V[i * size + c];
  } else if (cubic) {
    var u2 = u * u, u3 = u2 * u;
    var h00 = 2 * u3 - 3 * u2 + 1, h10 = (u3 - 2 * u2 + u) * dt, h01 = -2 * u3 + 3 * u2, h11 = (u3 - u2) * dt;
    var a = i * stride, b = (i + 1) * stride;
    for (c = 0; c < size; c++) {
      out[c] = h00 * V[a + size + c] + h10 * V[a + size * 2 + c] + h01 * V[b + size + c] + h11 * V[b + c];
    }
  } else {
    for (c = 0; c < size; c++) out[c] = V[i * size + c] * (1 - u) + V[(i + 1) * size + c] * u;
  }
  if (size === 4) {
    var l = Math.sqrt(out[0] * out[0] + out[1] * out[1] + out[2] * out[2] + out[3] * out[3]) || 1;
    for (c = 0; c < 4; c++) out[c] /= l;
  }
  return out;
}
