"""python -m unittest -v   (dentro de gateway/)"""
import json, os, pty, subprocess, sys, threading, time, unittest, urllib.request
from http.server import ThreadingHTTPServer

import api_fake
from gateway import comando, decidir, ler_nivel, tempos


class Regras(unittest.TestCase):
    def test_tempos_crescem_e_tem_teto(self):
        self.assertEqual(tempos(0, 0), (10, 0))       # sem pedestre: nao abre travessia
        self.assertEqual(tempos(5, 3), (20, 11))
        self.assertEqual(tempos(100, 100), (45, 25))  # teto: ninguem espera pra sempre

    def test_agua_no_limite_forca_atencao(self):
        self.assertEqual(decidir(29, "NORMAL", None)[0], 0)
        self.assertEqual(decidir(30, "NORMAL", None)[0], 1)

    def test_agua_alta_nao_rebaixa_evacuacao(self):
        self.assertEqual(decidir(80, "EVACUACAO", None)[0], 2)

    def test_sem_camera_e_sem_api_usa_ciclo_fixo(self):
        self.assertEqual(decidir(None, None, None), (0, 20, 10))

    def test_modo_desconhecido_da_api_vira_normal(self):
        self.assertEqual(decidir(0, "XPTO", (2, 1))[0], 0)

    def test_protocolo_serial(self):
        self.assertEqual(ler_nivel("L,42\r\n"), 42)
        for lixo in ("", "L,", "L,abc", "X,1", "L,1,2"):
            self.assertIsNone(ler_nivel(lixo))
        self.assertEqual(comando(2, 30, 0), b"M,2,30,0\n")


class PontaAPonta(unittest.TestCase):
    """UNO falso num pty + API fake: alerta da API e agua alta chegam como comando serial."""

    def test_fluxo_completo(self):
        api = ThreadingHTTPServer(("127.0.0.1", 0), api_fake.H)
        threading.Thread(target=api.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{api.server_port}"
        mestre, escravo = pty.openpty()
        gw = subprocess.Popen([sys.executable, "gateway.py", "--serial", os.ttyname(escravo), "--api", base, "--segundos", "8"],
                              stdout=subprocess.PIPE, text=True)
        try:
            for _ in range(5):                # UNO real manda a cada 1 s; o open do pyserial limpa o buffer
                os.write(mestre, b"L,10\n")
                time.sleep(0.5)
            urllib.request.urlopen(urllib.request.Request(f"{base}/alertas", data=b'{"modo":"EVACUACAO"}', method="POST"))
            time.sleep(2)
            os.write(mestre, b"L,50\n")
            out, _ = gw.communicate(timeout=15)
        finally:
            api.shutdown()
        log = [json.loads(l) for l in out.splitlines()]
        recebido = os.read(mestre, 4096).decode()
        self.assertEqual(log[1]["modo"], 0)
        self.assertTrue(any(l["modo"] == 2 for l in log))
        self.assertIn("M,0,20,10", recebido)
        self.assertIn("M,2,20,10", recebido)
        self.assertEqual(api_fake.ESTADO["leituras"][0]["nivelAguaCm"], 10)
        # API manda EVACUACAO; agua 50 cm nao rebaixa para ATENCAO
        self.assertEqual(log[-1]["nivelCm"], 50)
        self.assertEqual(log[-1]["modo"], 2)


if __name__ == "__main__":
    unittest.main()
