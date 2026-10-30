"""Prueba del ESP32 con firmware/main.py: manda una pieza a cada salida y muestra lo que responde.

Uso (desde C:\\dev\\inspeccion, con el venv activo y Thonny CERRADO):
    python probar_esp32.py COM5
Esperado: por cada salida 1, 2 y 3 la compuerta baja y sube sola, y aparece
{'e': 'div', 'id': N, 'out': N}. La salida 4 (rechazo) no mueve compuertas, solo confirma.
"""
import sys
import time

from core import protocolo as p
from core.enlace_serial import EnlaceESP32

puerto = sys.argv[1] if len(sys.argv) > 1 else "COM5"
enlace = EnlaceESP32(puerto)
time.sleep(1.5)                                   # por si el ESP32 se reinició al abrir el puerto
estado = None
for ev in enlace.atender():
    if ev["e"] == "tel":
        estado = ev["st"]
print("Conectado a", puerto, "- estado del ESP32:", estado or "sin telemetría todavía")

enlace.enviar(p.run())
for salida in (1, 2, 3, 4):
    print(f"\n--- pieza {salida} -> salida {salida} ---")
    enlace.enviar(p.clase(salida, salida))
    fin = time.time() + 7
    while time.time() < fin:
        for ev in enlace.atender():
            if ev["e"] != "tel":
                print("ESP32:", ev)
        time.sleep(0.02)
enlace.cerrar()
print("\nLíneas ignoradas (arranque o ruido):", enlace.lineas_ignoradas)
