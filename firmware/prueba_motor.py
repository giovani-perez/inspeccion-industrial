"""Prueba del motor de la banda con el L298N (MicroPython, ESP32). Para Thonny: Abrir -> F5.

NO se guarda como main.py: el firmware de las compuertas (main.py) es otro programa.

Conexiones:
    ESP32 GPIO25 -> ENA del L298N   (QUITA el jumper de ENA, si no el PWM no hace nada)
    ESP32 GPIO26 -> IN1
    ESP32 GPIO27 -> IN2
    ESP32 GND    -> GND del L298N   (tierra común, obligatoria)
    Eliminador 12 V -> +12V y GND del L298N;  OUT1 / OUT2 -> motor
    El pin 5V del L298N NO se conecta al ESP32 (el ESP32 se alimenta por el USB/aislador).

Comandos (escríbelos en la consola de Thonny y presiona Enter):
    1      mover TIEMPO_MS y parar solo
    2      mover sin límite (hasta que mandes 0)
    0      parar
    r      invertir el sentido (solo con el motor parado)
    v 80   velocidad al 80 %   (de 0 a 100; arranca en 95)
    f 8000 frecuencia del PWM en Hz (de 100 a 25000; arranca en 20000)
    ?      ver el estado

Arranque con "patada": los primeros ARRANQUE_MS van al 100 % para vencer la inercia del rodillo
y la fricción de la banda; después baja a la velocidad elegida.
Si el encoder está conectado (amarillo -> GPIO32, azul -> 3V3, negro -> GND) se imprimen los
pulsos por medio segundo: si caen casi a 0 una vez por vuelta, el problema es mecánico (algo se traba).
"""
import select
import sys
import time

from machine import PWM, Pin

PIN_ENA, PIN_IN1, PIN_IN2 = 25, 26, 27
FRECUENCIA_PWM = 20000         # Hz; a 20 kHz ya no se oye el chillido (a 1 kHz sí). Cámbiala en vivo con  f 8000
VELOCIDAD_PCT = 95             # casi a tope (22-oct: a 75 % se atascaba); la patada de arranque sigue al 100 %
TIEMPO_MS = 4000               # duración del comando 1
ARRANQUE_MS = 300              # "patada" al 100 % al arrancar (0 = sin patada)
PIN_ENCODER_A = 32
MOSTRAR_PULSOS = True          # imprime pulsos del encoder cada 0.5 s mientras gira

in1 = Pin(PIN_IN1, Pin.OUT, value=0)
in2 = Pin(PIN_IN2, Pin.OUT, value=0)
ena = PWM(Pin(PIN_ENA), freq=FRECUENCIA_PWM, duty_u16=0)

velocidad = VELOCIDAD_PCT
adelante = True
estado = "PARADO"              # PARADO, TEMPORIZADO o CONTINUO
inicio = 0
buffer = ""
pulsos = 0
ultimo_reporte = 0


def contar(_pin):
    global pulsos
    pulsos += 1


encoder_a = Pin(PIN_ENCODER_A, Pin.IN, Pin.PULL_UP)
encoder_a.irq(trigger=Pin.IRQ_RISING, handler=contar)


def duty(pct):
    return int(65535 * max(0, min(100, pct)) / 100)


def aplicar_sentido():
    in1.value(0 if adelante else 1)
    in2.value(1 if adelante else 0)


def arrancar(modo):
    global estado, inicio, pulsos, ultimo_reporte
    aplicar_sentido()
    inicio = ultimo_reporte = time.ticks_ms()
    pulsos = 0
    estado = modo
    print("Motor en marcha:", modo, "| velocidad", velocidad, "% | sentido",
          "adelante" if adelante else "atras")


def parar(motivo="detenido"):
    global estado
    ena.duty_u16(0)
    in1.value(0)
    in2.value(0)
    if estado != "PARADO":
        print("Motor", motivo)
    estado = "PARADO"


def atender(linea):
    global velocidad, adelante
    linea = linea.strip().lower()
    if not linea:
        return
    if linea == "1":
        arrancar("TEMPORIZADO")
    elif linea == "2":
        arrancar("CONTINUO")
    elif linea == "0":
        parar()
    elif linea == "r":
        if estado != "PARADO":
            print("Primero para el motor (0); invertir en marcha castiga el motor y el L298N")
        else:
            adelante = not adelante
            print("Sentido:", "adelante" if adelante else "atras")
    elif linea.startswith("v"):
        try:
            velocidad = max(0, min(100, int(linea[1:])))
            print("Velocidad:", velocidad, "%")
        except ValueError:
            print("Escribe la velocidad así: v 60")
    elif linea.startswith("f"):
        try:
            hz = max(100, min(25000, int(linea[1:])))
            ena.freq(hz)
            print("Frecuencia PWM:", hz, "Hz")
        except ValueError:
            print("Escribe la frecuencia así: f 8000")
    elif linea == "?":
        print("Estado:", estado, "| velocidad", velocidad, "% | PWM", ena.freq(), "Hz | sentido",
              "adelante" if adelante else "atras")
    else:
        print("Comando no reconocido:", linea)


def paso():
    """Patada de arranque, corte por tiempo y reporte del encoder."""
    global pulsos, ultimo_reporte
    if estado == "PARADO":
        return
    ahora = time.ticks_ms()
    transcurrido = time.ticks_diff(ahora, inicio)
    if estado == "TEMPORIZADO" and transcurrido >= TIEMPO_MS:
        parar("terminó su recorrido")
        return
    ena.duty_u16(duty(100 if transcurrido < ARRANQUE_MS else velocidad))
    if MOSTRAR_PULSOS and time.ticks_diff(ahora, ultimo_reporte) >= 500:
        print("pulsos encoder / 0.5 s:", pulsos)
        pulsos = 0
        ultimo_reporte = ahora


entrada = select.poll()
entrada.register(sys.stdin, select.POLLIN)
parar()
print("CONTROL DEL MOTOR - ESP32 + L298N")
print("1 = mover", TIEMPO_MS, "ms y PARA SOLO | 2 = continuo | 0 = parar | r = invertir | v 80 = velocidad | f 8000 = frecuencia | ? = estado")

try:
    while True:
        while entrada.poll(0):
            c = sys.stdin.read(1)
            if c in "\r\n":
                atender(buffer)
                buffer = ""
            else:
                buffer += c
                if len(buffer) > 20:
                    buffer = ""
        paso()
        time.sleep_ms(10)
finally:
    parar()
    ena.deinit()