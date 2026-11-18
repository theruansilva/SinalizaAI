"""API de mentira com o mesmo contrato da API Java, pra testar o gateway sem a VM.

uso: python api_fake.py [porta]   |   mudar modo: curl -X POST localhost:8080/alertas -d '{"modo":"EVACUACAO"}'
"""
import json, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ESTADO = {"modo": "NORMAL", "leituras": []}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, status, corpo=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if corpo is not None:
            self.wfile.write(json.dumps(corpo).encode())

    def corpo(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")

    def do_GET(self):
        if re.fullmatch(r"/cruzamentos/\d+/modo", self.path):
            return self.responder(200, {"modo": ESTADO["modo"], "verdeSeg": 30})
        if self.path == "/leituras":
            return self.responder(200, ESTADO["leituras"])
        self.responder(404, {"erro": "nao encontrado"})

    def do_POST(self):
        if re.fullmatch(r"/cruzamentos/\d+/leituras", self.path):
            ESTADO["leituras"].append(self.corpo())
            return self.responder(201, ESTADO["leituras"][-1])
        if self.path == "/alertas":
            modo = self.corpo().get("modo")
            if modo not in ("NORMAL", "ATENCAO", "EVACUACAO"):
                return self.responder(400, {"erro": "modo invalido"})
            ESTADO["modo"] = modo
            return self.responder(201, {"modo": modo})
        self.responder(404, {"erro": "nao encontrado"})


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"api fake em http://localhost:{porta}")
    ThreadingHTTPServer(("127.0.0.1", porta), H).serve_forever()
