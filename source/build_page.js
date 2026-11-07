// Writes index.html and main.js. main.js carries the model, so the page also works when
// index.html is opened straight from an unzipped folder (browsers block fetch on file://).
// Run: node build_page.js
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const here = __dirname, root = path.join(here, '..');
const read = f => fs.readFileSync(path.join(here, f), 'utf8');
const glb = fs.readFileSync(path.join(root, 'loop.glb')).toString('base64');
const main = '/* STEM Lab robot loop player. Plain WebGL, no libraries. The model (loop.glb) is on the last line. */\n'
  + read('glb-core.js') + '\n' + read('player.js')
  + "\nstartPlayer('" + glb + "');\n";
const html = read('page_template.html');
fs.writeFileSync(path.join(root, 'index.html'), html);
fs.writeFileSync(path.join(root, 'main.js'), main);
const gz = s => zlib.gzipSync(s).length;
console.log('index.html', html.length, 'bytes;', 'main.js', main.length, 'bytes;', gz(html) + gz(main), 'gzipped together');
