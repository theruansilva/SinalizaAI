"""Web UI da demo: cola o link, ve o video com as deteccoes (pessoas borradas) e os tempos decididos.

uso: python ui.py [porta] [host]  ->  http://localhost:8000   (host 0.0.0.0 ou IP do Tailscale para acessar de outro PC)
"""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from gateway import tempos
from visao import Contador

S = {"contador": None, "status": "cole um link (YouTube / HLS / mp4) e clique em Iniciar"}

PAGE = """<!doctype html><meta charset=utf-8><title>SinalizaAI - visao</title>
<body style="font-family:sans-serif;background:#111;color:#eee;margin:20px">
<h2>SinalizaAI - contagem na borda</h2>
<input id=u size=70 value="amostras/person-bicycle-car-detection.mp4"> <button onclick=go()>Iniciar</button>
<pre id=s style="font-size:18px"></pre><img src=/stream style="max-width:100%">
<p style="color:#888">Pessoas aparecem borradas; nenhum frame e gravado.</p>
<script>
function go(){fetch('/start?url='+encodeURIComponent(u.value),{method:'POST'})}
setInterval(async()=>{s.textContent=JSON.stringify(await (await fetch('/stats')).json(),null,1)},1000)
</script>"""


def iniciar(url):
    if S["contador"]:
        S["contador"].ativo = False  # encerra a sessao anterior
    S["contador"], S["status"] = None, "conectando..."
    try:
        c = Contador(url, intervalo=0.5, ao_vivo=True)
    except Exception as e:
        S["status"] = f"erro: {e}"
        return
    S["contador"], S["status"] = c, "rodando"


def stats():
    c = S["contador"]
    if c is None:
        return {"status": S["status"]}
    if not c.ativo:
        return {"status": "video terminou"}
    n = c.contagem()
    if n is None:
        return {"status": "aguardando primeira contagem"}
    verde, travessia = tempos(*n)
    return {"status": "rodando", "carros": n[0], "pedestres": n[1], "verdeSeg": verde, "travessiaSeg": travessia, "msInferencia": c.ms_inferencia}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/":
            return self.send(PAGE.encode(), "text/html; charset=utf-8")
        if p == "/stats":
            return self.send(json.dumps(stats()).encode(), "application/json")
        if p == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f")
            self.end_headers()
            ultimo = None
            try:
                while True:
                    c = S["contador"]
                    jpg = c.jpg if c else None
                    if jpg is None or jpg is ultimo:
                        time.sleep(0.05)
                        continue
                    ultimo = jpg
                    self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n%s\r\n" % (len(jpg), jpg))
            except (BrokenPipeError, ConnectionResetError):
                pass
        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/start" or "url" not in parse_qs(u.query):
            return self.send_error(400)
        threading.Thread(target=iniciar, args=(parse_qs(u.query)["url"][0],), daemon=True).start()
        self.send(b"ok", "text/plain")


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    print(f"http://{host}:{porta}")
    ThreadingHTTPServer((host, porta), H).serve_forever()
