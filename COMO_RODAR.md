# Como rodar (passo a passo)

## Pré-requisitos
- VS Code (ou Antigravity) com a extensão **Wokwi Simulator**
- Licença grátis do Wokwi: `F1` → **Wokwi: Request a new License** → entrar com conta Wokwi → **GET YOUR LICENSE** (vale 30 dias)
- Arduino IDE 2 **ou** `arduino-cli`
- Python 3.10+

## 1. Compilar o firmware (gera a pasta `build/`)
**arduino-cli** (na pasta `gs-semaforo`):
```bash
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno --output-dir build sketch
```
**Arduino IDE:** abra `sketch/sketch.ino`, placa *Arduino Uno*, menu *Sketch → Export Compiled Binary*, e copie `sketch.ino.hex` e `sketch.ino.elf` para uma pasta `build/` aqui na raiz.

## 2. Abrir o simulador
1. Abra a pasta **`gs-semaforo`** (onde está o `wokwi.toml`) no VS Code.
2. `F1` → **Wokwi: Start Simulator**. **Deixe a aba do simulador visível** (escondida = pausa).
3. Sem gateway, o semáforo já roda o ciclo fixo. Clique no HC-SR04 e coloque a distância abaixo de 170 cm: amarelo pisca e o buzzer toca (enchente).

## 3. Instalar o gateway (uma vez)
```bash
cd gateway
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. Rodar (cada um num terminal, dentro de `gateway/` com a venv ativa)
**Terminal 1 – API de teste**
```bash
python api_fake.py 8081
```
**Terminal 2 – gateway** (com o simulador rodando)
```bash
python gateway.py --serial rfc2217://localhost:4000 --api http://localhost:8081 --video amostras/cruzamento.mp4 --snapshot ../evidencias/snapshot_borrado.jpg
```
Uma linha JSON por segundo: `nivelCm` acompanha o sensor, `carros`/`pedestres` aparecem em ~5 s.

**Terminal 3 – simular alertas da Defesa Civil**
```bash
curl -X POST localhost:8081/alertas -d "{\"modo\":\"EVACUACAO\"}"   # verde contínuo
curl -X POST localhost:8081/alertas -d "{\"modo\":\"ATENCAO\"}"     # amarelo piscante
curl -X POST localhost:8081/alertas -d "{\"modo\":\"NORMAL\"}"      # ciclo adaptativo
curl localhost:8081/leituras                                         # leituras recebidas
```
`Ctrl+C` no gateway → em 10 s o UNO volta sozinho ao ciclo fixo.

## 5. Testes automáticos
```bash
python -m unittest -v      # dentro de gateway/; esperado: 7 testes OK
```
(O teste ponta a ponta usa `pty`, então só roda em Linux/macOS.)

## Problemas comuns
| Erro | Causa |
|---|---|
| `Connection refused` na porta 4000 | Simulador não está rodando, aba escondida, ou a pasta aberta não é `gs-semaforo` |
| Porta 8081 ocupada | Use outra: `api_fake.py 8090` e `--api http://localhost:8090` |
| Wokwi pede firmware | Faltou o passo 1 (pasta `build/`) |
| Primeira execução lenta | O YOLO baixa `yolo11n.pt` (~5 MB) sozinho |
