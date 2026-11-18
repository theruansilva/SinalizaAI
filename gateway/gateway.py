"""Gateway de borda: UNO (serial) <-> visao (YOLO) <-> API (HTTP).

uso: python gateway.py [--serial rfc2217://localhost:4000] [--video arquivo|url] [--api http://host:8080] [--cruzamento 1]
"""
import argparse, json, time, urllib.request

import serial

MODOS = {"NORMAL": 0, "ATENCAO": 1, "EVACUACAO": 2}
LIMITE_ENCHENTE_CM = 30          # mesmo valor do firmware
TEMPOS_PADRAO = (20, 10)         # sem camera: ciclo fixo


def tempos(carros, pessoas):
    """Tempo de verde dos carros e de travessia dos pedestres (s)."""
    verde = min(10 + 2 * carros, 45)
    travessia = 0 if pessoas == 0 else min(8 + pessoas, 25)
    return verde, travessia


def decidir(nivel_cm, modo_api, contagem):
    """-> (modo, verde, travessia). API manda no modo; agua alta nunca deixa ficar NORMAL."""
    modo = MODOS.get(modo_api, 0)
    if nivel_cm is not None and nivel_cm >= LIMITE_ENCHENTE_CM:
        modo = max(modo, MODOS["ATENCAO"])
    verde, travessia = tempos(*contagem) if contagem else TEMPOS_PADRAO
    return modo, verde, travessia


def ler_nivel(linha):
    """'L,42' -> 42; qualquer outra coisa -> None."""
    p = linha.strip().split(",")
    if len(p) == 2 and p[0] == "L" and p[1].lstrip("-").isdigit():
        return int(p[1])
    return None


def comando(modo, verde, travessia):
    return f"M,{modo},{verde},{travessia}\n".encode()


def http(metodo, url, corpo=None):
    req = urllib.request.Request(url, method=metodo, data=json.dumps(corpo).encode() if corpo else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2) as r:
        return json.loads(r.read() or "null")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="rfc2217://localhost:4000", help="URL pyserial (Wokwi) ou porta, ex. /dev/ttyACM0")
    ap.add_argument("--video", help="arquivo, HLS/MJPEG ou YouTube; sem isso usa tempos fixos")
    ap.add_argument("--api", help="URL base da API; sem isso roda offline")
    ap.add_argument("--cruzamento", type=int, default=1)
    ap.add_argument("--snapshot", help="salva o ultimo frame com pessoas borradas (evidencia)")
    ap.add_argument("--segundos", type=float, default=0, help="para depois de N s (0 = infinito)")
    a = ap.parse_args()

    uno = serial.serial_for_url(a.serial, baudrate=9600, timeout=0.2)
    contador = None
    if a.video:
        from visao import Contador
        contador = Contador(a.video, snapshot=a.snapshot)

    nivel, modo_api, ultimo_post, fim = None, None, 0, time.time() + a.segundos if a.segundos else None
    base = f"{a.api}/cruzamentos/{a.cruzamento}" if a.api else None
    while not fim or time.time() < fim:
        t0 = time.time()
        while uno.in_waiting:                       # drena o que o UNO mandou
            n = ler_nivel(uno.readline().decode(errors="ignore"))
            nivel = n if n is not None else nivel

        api_ok = False
        if base:
            try:
                modo_api, api_ok = http("GET", f"{base}/modo")["modo"], True
            except Exception:
                pass                                # API fora: mantem ultimo modo e segue local

        contagem = contador.contagem() if contador else None
        modo, verde, travessia = decidir(nivel, modo_api, contagem)
        uno.write(comando(modo, verde, travessia))

        carros, pessoas = contagem or (None, None)
        if base and api_ok and nivel is not None and time.time() - ultimo_post >= 5:
            try:
                http("POST", f"{base}/leituras", {"nivelAguaCm": nivel, "carros": carros, "pedestres": pessoas})
                ultimo_post = time.time()
            except Exception:
                pass
        print(json.dumps({"t": time.strftime("%H:%M:%S"), "nivelCm": nivel, "carros": carros, "pedestres": pessoas,
                          "modoApi": modo_api, "apiOk": api_ok, "modo": modo, "verdeSeg": verde, "travessiaSeg": travessia,
                          "msInferencia": contador.ms_inferencia if contador else None}), flush=True)
        time.sleep(max(0, 1 - (time.time() - t0)))


if __name__ == "__main__":
    main()
