"""Contagem de carros e pessoas com YOLO11n (borda). Nenhum frame e guardado, exceto --snapshot com pessoas borradas."""
import os, statistics, subprocess, sys, threading, time
from collections import deque

VEICULOS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # ids COCO
PESSOA = 0


def resolver(src):
    # shortcut: so YouTube via yt-dlp; o resto vai direto pro OpenCV/ffmpeg
    if "youtube.com" in src or "youtu.be" in src:
        return subprocess.check_output([sys.executable, "-m", "yt_dlp", "-g", "-f", "bestvideo[height<=720]/best", src], text=True).split()[0]
    return src


def borrar_pessoas(frame, caixas):
    import cv2
    for x1, y1, x2, y2 in caixas:
        roi = frame[y1:y2, x1:x2]
        if roi.size:
            frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (51, 51), 0)
    return frame


class Contador:
    """Roda em thread: le o video, conta a cada `intervalo` s e expoe a mediana das ultimas 5 contagens."""

    def __init__(self, fonte, intervalo=2.0, modelo="yolo11n.pt", snapshot=None, ao_vivo=False):
        import cv2
        from ultralytics import YOLO
        self.cv2, self.model = cv2, YOLO(modelo)
        self.cap = cv2.VideoCapture(resolver(fonte))
        assert self.cap.isOpened(), f"nao abriu o video: {fonte}"
        self.arquivo = os.path.exists(fonte)  # arquivo local: tocar em tempo real, nao o mais rapido possivel
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
        self.intervalo, self.snapshot, self.ao_vivo, self.jpg = intervalo, snapshot, ao_vivo, None
        self.hc, self.hp = deque(maxlen=5), deque(maxlen=5)
        self.ms_inferencia = None
        self.ativo = True
        self._frame = None
        threading.Thread(target=self._ler, daemon=True).start()
        threading.Thread(target=self._contar, daemon=True).start()

    def _ler(self):
        while self.ativo:  # parar(): ativo=False encerra leitura e contagem
            ok, f = self.cap.read()
            if not ok:
                break
            self._frame = f
            if self.arquivo:
                time.sleep(1 / self.fps)
        self.cap.release()
        self.ativo = False

    def _contar(self):
        while self.ativo:
            f, self._frame = self._frame, None
            if f is None:
                time.sleep(0.05)
                continue
            t0 = time.perf_counter()
            r = self.model(f, classes=[PESSOA, *VEICULOS], conf=0.35, verbose=False)[0]
            self.ms_inferencia = round((time.perf_counter() - t0) * 1000)
            ids = [int(c) for c in r.boxes.cls]
            self.hc.append(sum(c in VEICULOS for c in ids))
            self.hp.append(ids.count(PESSOA))
            if self.snapshot or self.ao_vivo:
                pessoas = [tuple(map(int, b)) for b, c in zip(r.boxes.xyxy.tolist(), ids) if c == PESSOA]
                img = borrar_pessoas(r.plot(), pessoas)
                if self.snapshot:
                    self.cv2.imwrite(self.snapshot, img)
                if self.ao_vivo:
                    self.jpg = self.cv2.imencode(".jpg", img)[1].tobytes()  # so em memoria, pra UI
            time.sleep(max(0, self.intervalo - (time.perf_counter() - t0)))

    def contagem(self):
        """(carros, pessoas) ou None se ainda nao contou / video acabou."""
        if not self.ativo or not self.hc:
            return None
        return round(statistics.median(self.hc)), round(statistics.median(self.hp))
