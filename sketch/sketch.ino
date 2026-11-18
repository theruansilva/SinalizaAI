// Semaforo CitizenTech - Arduino UNO
// Le o nivel da agua (HC-SR04), envia ao gateway e controla semaforo de carros + pedestres.
// Serial 9600:  UNO -> gateway  "L,<nivelCm>\n"   a cada 1 s
//               gateway -> UNO  "M,<modo>,<verdeSeg>,<travessiaSeg>\n"  modo 0=NORMAL 1=ATENCAO 2=EVACUACAO

const byte TRIG = 9, ECHO = 10, BUZZER = 8;
const byte C_VERM = 2, C_AMAR = 3, C_VERD = 4;  // carros
const byte P_VERM = 5, P_VERD = 6;              // pedestres

const int ALTURA_SENSOR_CM = 200;  // sensor preso no poste, 2 m acima da via
const int LIMITE_ENCHENTE_CM = 30; // agua >= 30 cm na via: alerta local
const unsigned long TIMEOUT_GATEWAY_MS = 10000;
const unsigned long AMARELO_MS = 3000, TODOS_VERM_MS = 2000;

enum Fase { VERDE, AMARELO, VERMELHO };
byte modo = 0;
int verdeSeg = 20, travessiaSeg = 10;      // ciclo seguro ate o gateway falar
unsigned long ultimoComando = 0, inicioFase = 0, ultimaLeitura = 0;
Fase fase = VERDE;
int nivelCm = 0;
String buf;

void luzes(bool cv, bool ca, bool cg, bool pv, bool pg) {
  digitalWrite(C_VERM, cv); digitalWrite(C_AMAR, ca); digitalWrite(C_VERD, cg);
  digitalWrite(P_VERM, pv); digitalWrite(P_VERD, pg);
}

int lerNivel() {
  digitalWrite(TRIG, LOW); delayMicroseconds(2);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 30000);
  if (us == 0) return nivelCm;  // sem eco: mantem a ultima leitura
  int dist = us / 58;
  return constrain(ALTURA_SENSOR_CM - dist, 0, ALTURA_SENSOR_CM);
}

void lerSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c != '\n') { if (buf.length() < 32) buf += c; continue; }
    int m, v, t;
    if (sscanf(buf.c_str(), "M,%d,%d,%d", &m, &v, &t) == 3 && m >= 0 && m <= 2) {
      modo = m;
      verdeSeg = constrain(v, 5, 90);       // nunca confia cegamente no que chega
      travessiaSeg = constrain(t, 0, 40);
      ultimoComando = millis();
    }
    buf = "";
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(TRIG, OUTPUT); pinMode(ECHO, INPUT); pinMode(BUZZER, OUTPUT);
  for (byte p = 2; p <= 6; p++) pinMode(p, OUTPUT);
}

void loop() {
  unsigned long agora = millis();
  lerSerial();

  if (agora - ultimaLeitura >= 1000) {
    ultimaLeitura = agora;
    nivelCm = lerNivel();
    Serial.print("L,"); Serial.println(nivelCm);
  }

  // sem gateway: volta ao ciclo fixo seguro
  if (ultimoComando == 0 || agora - ultimoComando > TIMEOUT_GATEWAY_MS) {
    modo = 0; verdeSeg = 20; travessiaSeg = 10;
  }

  bool enchente = nivelCm >= LIMITE_ENCHENTE_CM;  // regra local, funciona mesmo offline
  bool pisca = (agora / 500) % 2;

  if (enchente || modo == 1) {          // ATENCAO: amarelo piscante, ninguem atravessa
    luzes(LOW, pisca, LOW, HIGH, LOW);
    if (enchente) tone(BUZZER, 1000); else noTone(BUZZER);
    fase = VERDE; inicioFase = agora;
    return;
  }
  noTone(BUZZER);
  if (modo == 2) {                      // EVACUACAO: onda verde ate o abrigo
    luzes(LOW, LOW, HIGH, HIGH, LOW);
    fase = VERDE; inicioFase = agora;
    return;
  }

  unsigned long dur = fase == VERDE ? verdeSeg * 1000UL
                    : fase == AMARELO ? AMARELO_MS
                    : max((unsigned long)travessiaSeg * 1000UL, TODOS_VERM_MS);
  if (agora - inicioFase >= dur) {
    fase = fase == VERDE ? AMARELO : fase == AMARELO ? VERMELHO : VERDE;
    inicioFase = agora;
  }
  bool pedVerde = fase == VERMELHO && travessiaSeg > 0;
  luzes(fase == VERMELHO, fase == AMARELO, fase == VERDE, !pedVerde, pedVerde);
}
