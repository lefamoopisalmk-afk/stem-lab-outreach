function startPlayer(GLB_BASE64) {
  'use strict';

  var stage = document.getElementById('stage'), canvas = document.getElementById('view');
  var btn = document.getElementById('toggle'), bar = document.getElementById('bar'), timeEl = document.getElementById('time');
  var rPos = document.getElementById('r-pos'), rRot = document.getElementById('r-rot'), rScl = document.getElementById('r-scl');

  function fail(msg) {
    document.documentElement.classList.add('no-webgl');
    if (msg) document.getElementById('fallback-msg').textContent = msg;
    btn.disabled = true; btn.style.display = 'none';
  }

  /* ---------- matrices (column major) ---------- */
  function trs(t, q, s, o) {
    var x = q[0], y = q[1], z = q[2], w = q[3], x2 = x + x, y2 = y + y, z2 = z + z;
    var xx = x * x2, xy = x * y2, xz = x * z2, yy = y * y2, yz = y * z2, zz = z * z2, wx = w * x2, wy = w * y2, wz = w * z2;
    o[0] = (1 - yy - zz) * s[0]; o[1] = (xy + wz) * s[0]; o[2] = (xz - wy) * s[0]; o[3] = 0;
    o[4] = (xy - wz) * s[1]; o[5] = (1 - xx - zz) * s[1]; o[6] = (yz + wx) * s[1]; o[7] = 0;
    o[8] = (xz + wy) * s[2]; o[9] = (yz - wx) * s[2]; o[10] = (1 - xx - yy) * s[2]; o[11] = 0;
    o[12] = t[0]; o[13] = t[1]; o[14] = t[2]; o[15] = 1;
    return o;
  }
  function mul(a, b, o) {
    for (var c = 0; c < 4; c++) {
      var b0 = b[c * 4], b1 = b[c * 4 + 1], b2 = b[c * 4 + 2], b3 = b[c * 4 + 3];
      o[c * 4] = a[0] * b0 + a[4] * b1 + a[8] * b2 + a[12] * b3;
      o[c * 4 + 1] = a[1] * b0 + a[5] * b1 + a[9] * b2 + a[13] * b3;
      o[c * 4 + 2] = a[2] * b0 + a[6] * b1 + a[10] * b2 + a[14] * b3;
      o[c * 4 + 3] = a[3] * b0 + a[7] * b1 + a[11] * b2 + a[15] * b3;
    }
    return o;
  }
  function normalMat(m, o) {                     // inverse transpose of the upper 3x3, for squashed parents
    var a = m[0], b = m[1], c = m[2], d = m[4], e = m[5], f = m[6], g = m[8], h = m[9], i = m[10];
    var A = e * i - f * h, B = c * h - b * i, C = b * f - c * e, det = a * A + d * B + g * C;
    det = det ? 1 / det : 1;
    o[0] = A * det; o[1] = (f * g - d * i) * det; o[2] = (d * h - e * g) * det;
    o[3] = B * det; o[4] = (a * i - c * g) * det; o[5] = (b * g - a * h) * det;
    o[6] = C * det; o[7] = (c * d - a * f) * det; o[8] = (a * e - b * d) * det;
    return o;
  }
  function lookAt(eye, at) {
    var z = norm([eye[0] - at[0], eye[1] - at[1], eye[2] - at[2]]);
    var x = norm([z[2], 0, -z[0]]);              // up is +Y
    var y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
    return new Float32Array([x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
      -dot(x, eye), -dot(y, eye), -dot(z, eye), 1]);
  }
  function persp(fovy, aspect, n, f) {
    var t = 1 / Math.tan(fovy / 2);
    return new Float32Array([t / aspect, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0]);
  }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function norm(a) { var l = Math.sqrt(dot(a, a)) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }

  /* ---------- model ---------- */
  var bytes, glb, clip;
  try {
    var bin = atob(GLB_BASE64);
    bytes = new Uint8Array(bin.length);
    for (var bi = 0; bi < bin.length; bi++) bytes[bi] = bin.charCodeAt(bi);
    glb = parseGLB(bytes);
    clip = makeClip(glb, 0);
  } catch (e) { fail('The 3D model could not be read, so here is the robot as a picture.'); return; }

  var J = glb.json;
  var nodes = J.nodes.map(function (n) {
    return {
      name: n.name, mesh: n.mesh, children: n.children || [],
      t: (n.translation || [0, 0, 0]).slice(), r: (n.rotation || [0, 0, 0, 1]).slice(), s: (n.scale || [1, 1, 1]).slice(),
      local: new Float32Array(16), world: new Float32Array(16), nm: new Float32Array(9)
    };
  });
  var order = [];
  (function walk(list, parent) {
    list.forEach(function (i) { order.push({ n: nodes[i], parent: parent }); walk(nodes[i].children, nodes[i]); });
  })(J.scenes[J.scene || 0].nodes, null);
  var root = nodes.filter(function (n) { return n.name === 'Robot_Head'; })[0];

  /* ---------- WebGL ---------- */
  var VS = 'attribute vec3 aP;attribute vec3 aN;uniform mat4 uVP;uniform mat4 uM;uniform mat3 uNM;varying vec3 vN;varying vec3 vW;' +
    'void main(){vec4 w=uM*vec4(aP,1.0);vW=w.xyz;vN=uNM*aN;gl_Position=uVP*w;}';
  var FS = 'precision mediump float;varying vec3 vN;varying vec3 vW;uniform vec3 uBase;uniform vec3 uEmit;uniform vec2 uMR;uniform vec3 uEye;' +
    'float spec(vec3 n,vec3 v,vec3 l,float p){vec3 h=normalize(v+l);return pow(max(dot(n,h),0.0),p)*max(dot(n,l),0.0);}' +
    'void main(){vec3 n=normalize(vN);vec3 v=normalize(uEye-vW);' +
    'float m=uMR.x;float r=uMR.y;float p=2.0/max(r*r*r*r,0.002)-2.0;p=min(p,180.0);' +
    'vec3 k=normalize(vec3(.55,.8,.62));vec3 f=normalize(vec3(-.75,.2,.55));vec3 b=normalize(vec3(.1,.55,-.85));' +
    'vec3 sky=mix(vec3(.10,.13,.20),vec3(.42,.52,.68),n.y*.5+.5);' +
    'vec3 d=sky+vec3(1.0,.96,.9)*1.05*max(dot(n,k),0.0)+vec3(.55,.68,.95)*.32*max(dot(n,f),0.0);' +
    'vec3 c=uBase*(1.0-m)*d;vec3 s0=mix(vec3(.04),uBase,m);float sn=(p+8.0)/40.0;' +
    'c+=s0*(sn*spec(n,v,k,p)*1.6+sky*.5);' +
    'float rim=pow(1.0-max(dot(n,v),0.0),3.0)*max(dot(n,b)+.35,0.0);c+=vec3(.5,.7,1.0)*rim*.55;' +
    'c+=uEmit;gl_FragColor=vec4(pow(clamp(c,0.0,1.0),vec3(1.0/2.2)),1.0);}';
  var SVS = 'attribute vec2 aQ;uniform mat4 uVP;uniform vec4 uS;varying vec2 vQ;' +
    'void main(){vQ=aQ;gl_Position=uVP*vec4(uS.x+aQ.x*uS.w,uS.y,uS.z+aQ.y*uS.w,1.0);}';
  var SFS = 'precision mediump float;varying vec2 vQ;uniform float uA;' +
    'void main(){float d=length(vQ);float a=uA*(1.0-smoothstep(.25,1.0,d));gl_FragColor=vec4(0.0,0.0,0.0,a);}';

  var gl, prog, sprog, U, SU, A, draws = [], quad;
  function shader(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  function program(vs, fs) {
    var p = gl.createProgram();
    gl.attachShader(p, shader(gl.VERTEX_SHADER, vs)); gl.attachShader(p, shader(gl.FRAGMENT_SHADER, fs));
    gl.bindAttribLocation(p, 0, vs === VS ? 'aP' : 'aQ');
    if (vs === VS) gl.bindAttribLocation(p, 1, 'aN');
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }
  function vbo(data) { var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW); return b; }
  function initGL() {
    prog = program(VS, FS); sprog = program(SVS, SFS);
    U = {}; ['uVP', 'uM', 'uNM', 'uBase', 'uEmit', 'uMR', 'uEye'].forEach(function (u) { U[u] = gl.getUniformLocation(prog, u); });
    SU = { uVP: gl.getUniformLocation(sprog, 'uVP'), uS: gl.getUniformLocation(sprog, 'uS'), uA: gl.getUniformLocation(sprog, 'uA') };
    quad = vbo(new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
    draws = [];
    order.forEach(function (o) {
      if (o.n.mesh === undefined) return;
      J.meshes[o.n.mesh].primitives.forEach(function (p) {
        var mat = J.materials[p.material] || {}, pbr = mat.pbrMetallicRoughness || {};
        var idx = glb.accessor(p.indices), type = gl.UNSIGNED_SHORT;
        if (idx instanceof Uint8Array) idx = new Uint16Array(idx);
        if (idx instanceof Uint32Array) { idx = new Uint16Array(idx); }
        var ib = gl.createBuffer();
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
        var bc = pbr.baseColorFactor || [1, 1, 1, 1];
        draws.push({
          node: o.n, pos: vbo(glb.accessor(p.attributes.POSITION)), nrm: vbo(glb.accessor(p.attributes.NORMAL)),
          ib: ib, count: idx.length, type: type, base: [bc[0], bc[1], bc[2]], emit: mat.emissiveFactor || [0, 0, 0],
          mr: [pbr.metallicFactor === undefined ? 1 : pbr.metallicFactor, pbr.roughnessFactor === undefined ? 1 : pbr.roughnessFactor]
        });
      });
    });
    gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.clearColor(0, 0, 0, 0);
  }

  try {
    var opts = { antialias: true, alpha: true, premultipliedAlpha: true, powerPreference: 'low-power', depth: true };
    gl = canvas.getContext('webgl', opts) || canvas.getContext('experimental-webgl', opts);
    if (!gl) { fail(); return; }
    initGL();
  } catch (e) { fail(); return; }

  /* ---------- camera that always fits the whole motion ---------- */
  var FOVY = 26 * Math.PI / 180, TARGET = [0, .18, 0], DIR = norm([.2, .13, 1]);
  var HALF_H = 1.58, HALF_W = 1.5;
  var VP = new Float32Array(16), EYE = [0, 0, 8], renderScale = 1, dirty = true;
  function resize() {
    var w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2) * renderScale;
    var pw = Math.max(1, Math.round(w * dpr)), ph = Math.max(1, Math.round(h * dpr));
    if (canvas.width !== pw || canvas.height !== ph) { canvas.width = pw; canvas.height = ph; }
    gl.viewport(0, 0, pw, ph);
    var aspect = w / h, t = Math.tan(FOVY / 2);
    var d = Math.max(HALF_H / t, HALF_W / (t * aspect)) + .9;   // .9 keeps the lean toward the camera inside the frame
    EYE = [TARGET[0] + DIR[0] * d, TARGET[1] + DIR[1] * d, TARGET[2] + DIR[2] * d];
    mul(persp(FOVY, aspect, Math.max(.1, d - 3), d + 5), lookAt(EYE, TARGET), VP);
    dirty = true;
  }

  /* ---------- pose + draw ---------- */
  var tmp = new Float32Array(4);
  function pose(t) {
    for (var i = 0; i < clip.channels.length; i++) {
      var c = clip.channels[i], n = nodes[c.node], dst = c.path === 'rotation' ? n.r : c.path === 'scale' ? n.s : n.t;
      sampleChannel(c, t, tmp);
      for (var k = 0; k < c.size; k++) dst[k] = tmp[k];
    }
    for (var o = 0; o < order.length; o++) {
      var e = order[o]; trs(e.n.t, e.n.r, e.n.s, e.n.local);
      if (e.parent) mul(e.parent.world, e.n.local, e.n.world); else e.n.world.set(e.n.local);
      normalMat(e.n.world, e.n.nm);
    }
  }
  function draw() {
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    // soft contact shadow: it tightens and darkens as the robot comes down
    var lift = Math.max(0, root.t[1]), rad = 1.25 * root.s[0] + lift * .55, alpha = .46 / (1 + lift * 1.7);
    gl.useProgram(sprog); gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE); gl.enable(gl.BLEND);
    gl.uniformMatrix4fv(SU.uVP, false, VP);
    gl.uniform4f(SU.uS, root.t[0], -1.14, root.t[2], rad); gl.uniform1f(SU.uA, alpha);
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.enableVertexAttribArray(0); gl.disableVertexAttribArray(1);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.disable(gl.BLEND); gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE);

    gl.useProgram(prog);
    gl.uniformMatrix4fv(U.uVP, false, VP); gl.uniform3f(U.uEye, EYE[0], EYE[1], EYE[2]);
    gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1);
    for (var i = 0; i < draws.length; i++) {
      var d = draws[i];
      gl.uniformMatrix4fv(U.uM, false, d.node.world); gl.uniformMatrix3fv(U.uNM, false, d.node.nm);
      gl.uniform3fv(U.uBase, d.base); gl.uniform3fv(U.uEmit, d.emit); gl.uniform2fv(U.uMR, d.mr);
      gl.bindBuffer(gl.ARRAY_BUFFER, d.pos); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, d.nrm); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, d.ib);
      gl.drawElements(gl.TRIANGLES, d.count, d.type, 0);
    }
  }

  /* ---------- readout ---------- */
  function mmss(s) { s = Math.floor(s); return Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }
  var lastUi = -1;
  function ui(t, force) {
    if (!force && Math.abs(t - lastUi) < .12) return;
    lastUi = t;
    bar.style.transform = 'scaleX(' + (t / clip.duration).toFixed(4) + ')';
    timeEl.textContent = mmss(t) + ' / ' + mmss(clip.duration);
    rPos.textContent = (root.t[1] >= 0 ? '+' : '−') + Math.abs(root.t[1]).toFixed(2);
    var w = Math.min(1, Math.abs(root.r[3]));
    rRot.textContent = Math.round(2 * Math.acos(w) * 180 / Math.PI) + '°';
    rScl.textContent = ((root.s[0] + root.s[1] + root.s[2]) / 3).toFixed(2);
  }

  /* ---------- clock: the loop wraps with a modulo, so time never jumps ---------- */
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) document.getElementById('note').hidden = false;
  var playing = !reduce, clock = 0, prev = 0, slow = 0, frames = 0;
  function setPlaying(p) {
    playing = p;
    btn.textContent = p ? 'Pause' : 'Play';
    btn.setAttribute('aria-pressed', String(!p));
    prev = 0;
    if (p) kick();
  }
  var raf = 0;
  function kick() { if (!raf) raf = requestAnimationFrame(frame); }
  function frame(now) {
    raf = 0;
    if (playing) {
      if (prev) {
        var dt = (now - prev) / 1000;
        // a long gap (background tab, very slow PC) moves on by one short step, so the
        // animation never skips ahead and never stalls however few frames it gets
        clock = (clock + Math.min(dt, .25)) % clip.duration;
        if (dt < .25) {
          slow += dt; frames++;
          if (frames >= 45) {                    // slow school PC: draw fewer pixels rather than drop frames
            if (slow / frames > 1 / 24 && renderScale > .55) { renderScale *= .8; resize(); }
            slow = 0; frames = 0;
          }
        }
      }
      prev = now;
      dirty = true;
    }
    if (dirty) { pose(clock); draw(); ui(clock); dirty = false; }
    if (playing) kick();
  }

  btn.addEventListener('click', function () { document.getElementById('note').hidden = true; setPlaying(!playing); });
  if (window.ResizeObserver) new ResizeObserver(function () { resize(); kick(); }).observe(stage);
  window.addEventListener('resize', function () { resize(); kick(); });
  window.addEventListener('orientationchange', function () { resize(); kick(); });
  canvas.addEventListener('webglcontextlost', function (e) { e.preventDefault(); if (raf) cancelAnimationFrame(raf); raf = 0; });
  canvas.addEventListener('webglcontextrestored', function () { initGL(); resize(); kick(); });

  window.__loop = {
    duration: clip.duration,
    seek: function (t) { setPlaying(false); clock = t; pose(t); dirty = true; ui(t, true); kick(); },
    play: function () { setPlaying(true); },
    time: function () { return clock; },
    size: function () { return [canvas.width, canvas.height]; }
  };

  resize();
  setPlaying(playing);
  pose(clock); draw(); ui(clock, true);
  kick();
}
