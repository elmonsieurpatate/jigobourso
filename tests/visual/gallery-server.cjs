// HTTP local commun aux sondes : même chargement des polices et des assets que le site.
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
module.exports = async function galleryServer() {
  if (process.env.GALLERY_URL) return { url: process.env.GALLERY_URL, close: async () => {} };
  const root = path.resolve(__dirname, '../..');
  const server = http.createServer((req, res) => {
    const name = new URL(req.url, 'http://localhost').pathname;
    if (name !== '/design/galerie.html' && !/^\/app\/public\/assets\/[\w./-]+$/.test(name)) { res.writeHead(404).end(); return; }
    const file = path.resolve(root, '.' + name);
    if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
    const type = { '.css': 'text/css', '.js': 'application/javascript', '.html': 'text/html', '.ttf': 'font/ttf', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream';
    fs.readFile(file, (err, data) => { res.writeHead(err ? 404 : 200, { 'Content-Type': type }); res.end(err ? '' : data); });
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  server.unref();
  return { url: `http://127.0.0.1:${server.address().port}/design/galerie.html`, close: () => new Promise(resolve => server.close(resolve)) };
};
