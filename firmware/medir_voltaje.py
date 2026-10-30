"""Voltímetro con el ESP32 (Thonny, F5): mide la salida del XL4015 sin multímetro.

Divisor con 4 resistencias IGUALES (cualquier valor entre 1 kΩ y 100 kΩ):

    OUT+ del XL4015 ── R ── R ── R ──┬── R ── OUT- del XL4015
                                     └── GPIO34 del ESP32

    y OUT- del XL4015 unido a un GND del ESP32 (sin eso la lectura no sirve).

El pin recibe 1/4 del voltaje: hasta 12 V llegan como 3 V, que el ESP32 aguanta.
NUNCA conectes OUT+ directo a un pin del ESP32.
Desconecta los servos mientras ajustas el potenciómetro. Stop en Thonny para terminar.
"""
import time

from machine import ADC, Pin

FACTOR = 4                    # 3 resistencias arriba + 1 abajo
adc = ADC(Pin(34), atten=ADC.ATTN_11DB)

print("Gira el tornillo del potenciometro azul despacio hasta que diga OK (5.0 - 5.5 V)")
while True:
    v = sum(adc.read_uv() for _ in range(32)) / 32 / 1000000 * FACTOR
    if v < 0.3:
        estado = "sin voltaje: revisa el divisor, la tierra comun o que el XL4015 tenga entrada"
    elif v < 4.8:
        estado = "BAJO: gira el potenciometro para subir"
    elif v <= 5.6:
        estado = "OK para servos"
    elif v <= 6.0:
        estado = "un poco alto: baja un poco"
    else:
        estado = "PELIGRO: NO conectes servos, baja el voltaje"
    print("salida XL4015 = {:.2f} V  ->  {}".format(v, estado))
    time.sleep(0.5)
