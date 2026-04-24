#!/usr/bin/env python3
"""AAA服装厂 Server — static files + gallery with voting & admin delete."""
import http.server, json, os, base64, time, uuid

PORT = int(os.environ.get('PORT', 8765))
BASE = os.path.dirname(os.path.abspath(__file__))
# Use persistent disk path if available (Render), otherwise local
GALLERY = os.environ.get('GALLERY_PATH', os.path.join(BASE, 'gallery'))
os.makedirs(GALLERY, exist_ok=True)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Cache static assets for 1 hour
        p = self.path.split('?')[0]
        if p.endswith(('.jpg','.png','.js','.css','.woff2','.ttf','.otf','.html')):
            self.send_header('Cache-Control', 'public, max-age=3600')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == '/':
            self.path = '/tshirt-designer.html'
        if self.path == '/api/gallery':
            return self._get_gallery()
        # Serve gallery files from GALLERY dir (may be external path)
        if self.path.startswith('/gallery/'):
            fname = self.path[len('/gallery/'):]
            fpath = os.path.join(GALLERY, fname)
            if os.path.isfile(fpath):
                self.send_response(200)
                ct = 'image/png' if fname.endswith('.png') else 'application/octet-stream'
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', str(os.path.getsize(fpath)))
                self.end_headers()
                with open(fpath, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404)
                return
        super().do_GET()

    def do_POST(self):
        if self.path == '/api/publish': return self._publish()
        if self.path == '/api/delete': return self._delete()
        if self.path == '/api/vote': return self._vote()
        self.send_error(404)

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))

    def _get_gallery(self):
        items = []
        for f in os.listdir(GALLERY):
            if not f.endswith('.json'): continue
            try:
                with open(os.path.join(GALLERY, f), 'r', encoding='utf-8') as fh:
                    m = json.load(fh)
                m['imageUrl'] = f'/gallery/{m["id"]}.png'
                m.setdefault('wants', [])
                m.setdefault('unwants', [])
                m.setdefault('uid', '')
                items.append(m)
            except: pass
        items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        self._json(200, items)

    def _publish(self):
        try:
            data = self._body()
            did = uuid.uuid4().hex[:8]
            img_b64 = data.get('image', '')
            if ',' in img_b64: img_b64 = img_b64.split(',', 1)[1]
            with open(os.path.join(GALLERY, f'{did}.png'), 'wb') as f:
                f.write(base64.b64decode(img_b64))
            meta = dict(id=did, title=data.get('title', '未命名'),
                        author=data.get('author', '匿名设计师'),
                        uid=data.get('uid', ''),
                        product=data.get('product', 'tee'),
                        color=data.get('color', '#FFFFFF'),
                        timestamp=time.time(),
                        wants=[], unwants=[])
            with open(os.path.join(GALLERY, f'{did}.json'), 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False)
            self._json(200, {'ok': True, 'id': did})
        except Exception as e:
            self._json(500, {'ok': False, 'error': str(e)})

    def _delete(self):
        try:
            data = self._body()
            did, uid, is_admin = data.get('id',''), data.get('uid',''), data.get('admin', False)
            jp = os.path.join(GALLERY, f'{did}.json')
            pp = os.path.join(GALLERY, f'{did}.png')
            if not os.path.exists(jp):
                self._json(404, {'ok': False, 'error': '作品不存在'}); return
            with open(jp, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            if not is_admin and meta.get('uid','') != uid:
                self._json(403, {'ok': False, 'error': '无权删除他人作品'}); return
            os.remove(jp)
            if os.path.exists(pp): os.remove(pp)
            self._json(200, {'ok': True})
        except Exception as e:
            self._json(500, {'ok': False, 'error': str(e)})

    def _vote(self):
        try:
            data = self._body()
            did, uid, vote = data.get('id',''), data.get('uid',''), data.get('vote','')
            jp = os.path.join(GALLERY, f'{did}.json')
            if not os.path.exists(jp):
                self._json(404, {'ok': False}); return
            with open(jp, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            wants = meta.get('wants', [])
            unwants = meta.get('unwants', [])
            was_want = uid in wants
            was_unwant = uid in unwants
            if uid in wants: wants.remove(uid)
            if uid in unwants: unwants.remove(uid)
            if vote == 'want' and not was_want: wants.append(uid)
            elif vote == 'unwant' and not was_unwant: unwants.append(uid)
            meta['wants'] = wants
            meta['unwants'] = unwants
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False)
            self._json(200, {'ok': True, 'wants': len(wants), 'unwants': len(unwants)})
        except Exception as e:
            self._json(500, {'ok': False, 'error': str(e)})

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    print(f'AAA服装厂 running at http://localhost:{PORT}')
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
