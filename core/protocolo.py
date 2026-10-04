"""Protocolo PC <-> ESP32: un mensaje JSON por línea (UTF-8, terminado en salto de línea).

Los comandos (PC -> ESP32) usan la clave "c" y los eventos (ESP32 -> PC) usan la clave "e".
"""
import json

NUM = (int, float)

# Campos obligatorios de cada mensaje y su tipo
COMANDOS = {
    "hb": {},                                  # latido
    "run": {},                                 # arrancar la banda
    "stop": {},                                # detener la banda
    "cls": {"id": int, "out": int},            # salida asignada a la siguiente pieza
    "vel": {"nom": NUM, "insp": NUM},          # velocidades en mm/s
    "gate": {"n": int, "a": NUM},              # compuerta n a un ángulo (solo mantenimiento)
}
EVENTOS = {
    "tel": {"v": NUM, "d": NUM, "st": str},    # telemetría
    "exit": {"id": int, "enc": int},           # la pieza cruzó el sensor IR
    "div": {"id": int, "out": int},            # compuerta ejecutada
    "rej": {"why": str},                       # pieza enviada a rechazo
    "estop": {},                               # paro de emergencia
    "err": {"code": str},                      # falla
}
MAX_LINEA = 1024


class ErrorProtocolo(ValueError):
    """El mensaje no cumple el protocolo."""


def _tipo_ok(valor, tipos):
    # bool es subclase de int en Python: no se acepta como número
    return not isinstance(valor, bool) and isinstance(valor, tipos)


def validar(mensaje):
    """Revisa que el mensaje cumpla el protocolo. Regresa el mismo mensaje o lanza ErrorProtocolo."""
    if not isinstance(mensaje, dict):
        raise ErrorProtocolo("el mensaje debe ser un objeto JSON")
    if ("c" in mensaje) == ("e" in mensaje):
        raise ErrorProtocolo("debe tener exactamente una clave: 'c' (comando) o 'e' (evento)")
    clave = "c" if "c" in mensaje else "e"
    tabla = COMANDOS if clave == "c" else EVENTOS
    nombre = mensaje[clave]
    if not isinstance(nombre, str) or nombre not in tabla:
        raise ErrorProtocolo(f"mensaje desconocido: {nombre!r}")

    for campo, tipos in tabla[nombre].items():
        if campo not in mensaje:
            raise ErrorProtocolo(f"{nombre}: falta el campo '{campo}'")
        if not _tipo_ok(mensaje[campo], tipos):
            raise ErrorProtocolo(f"{nombre}: el campo '{campo}' tiene un tipo inválido")
    extra = set(mensaje) - set(tabla[nombre]) - {clave}
    if extra:
        raise ErrorProtocolo(f"{nombre}: campos no permitidos {sorted(extra)}")

    if nombre in ("cls", "div") and not 1 <= mensaje["out"] <= 4:
        raise ErrorProtocolo(f"{nombre}: 'out' debe estar entre 1 y 4")
    if nombre == "gate":
        if not 1 <= mensaje["n"] <= 3:
            raise ErrorProtocolo("gate: 'n' debe estar entre 1 y 3")
        if not -90 <= mensaje["a"] <= 90:
            raise ErrorProtocolo("gate: 'a' debe estar entre -90 y 90")
    if nombre == "vel" and (mensaje["nom"] <= 0 or mensaje["insp"] <= 0):
        raise ErrorProtocolo("vel: las velocidades deben ser positivas")
    return mensaje


def codificar(mensaje):
    """dict -> bytes listos para enviar por serial."""
    validar(mensaje)
    return (json.dumps(mensaje, separators=(",", ":")) + "\n").encode("utf-8")


def decodificar(linea):
    """Línea (bytes o str) -> dict validado."""
    if isinstance(linea, (bytes, bytearray)):
        try:
            linea = bytes(linea).decode("utf-8")
        except UnicodeDecodeError as e:
            raise ErrorProtocolo("la línea no es UTF-8 válido") from e
    try:
        mensaje = json.loads(linea)
    except json.JSONDecodeError as e:
        raise ErrorProtocolo(f"JSON inválido: {e.msg}") from e
    return validar(mensaje)


class LectorLineas:
    """Junta los bytes que llegan por serial (a pedazos) y entrega líneas completas."""

    def __init__(self):
        self._buf = b""

    def alimentar(self, datos):
        self._buf += datos
        *lineas, self._buf = self._buf.split(b"\n")
        if len(self._buf) > MAX_LINEA:      # basura sin salto de línea: se descarta
            self._buf = b""
        return [l.strip(b"\r") for l in lineas if l.strip()]


# --- Comandos PC -> ESP32 ---------------------------------------------------------------------
def hb():
    return {"c": "hb"}


def run():
    return {"c": "run"}


def stop():
    return {"c": "stop"}


def clase(id_pieza, salida):
    return {"c": "cls", "id": id_pieza, "out": salida}


def vel(nominal, inspeccion):
    return {"c": "vel", "nom": nominal, "insp": inspeccion}


def gate(n, angulo):
    return {"c": "gate", "n": n, "a": angulo}


# --- Eventos ESP32 -> PC ----------------------------------------------------------------------
def tel(velocidad, distancia, estado):
    return {"e": "tel", "v": velocidad, "d": distancia, "st": estado}


def exit_pieza(id_pieza, cuentas):
    return {"e": "exit", "id": id_pieza, "enc": cuentas}


def div(id_pieza, salida):
    return {"e": "div", "id": id_pieza, "out": salida}


def rej(motivo):
    return {"e": "rej", "why": motivo}


def estop():
    return {"e": "estop"}


def err(codigo):
    return {"e": "err", "code": codigo}
