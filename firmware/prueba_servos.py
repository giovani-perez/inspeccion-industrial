"""Prueba de las compuertas (servos MG90S) para Thonny + ESP32 (MicroPython). NO se guarda como main.py.

VELOCIDAD MODERADA: los servos avanzan poco a poco (VELOCIDAD grados por segundo) en lugar de
saltar de golpe. Así se ve bien el recorrido y no le pegan a la pieza ni a la estructura.

MODO UNO A UNO (activado al iniciar): solo la compuerta que mandas recibe pulso; las otras se
sueltan. Un servo sin pulso no hace fuerza y casi no consume corriente, así que la fuente
solo alimenta a un servo trabajando a la vez.
(El código controla la SEÑAL, no los 5 V: el rojo de los servos sigue conectado al XL4015.)

Al correrlo (F5) NO mueve nada: espera comandos en la consola de Thonny (escribe y Enter):
    d 1        prueba de DIRECCION de la compuerta 1: desde su reposo gira hacia un lado, regresa,
               gira hacia el otro lado y regresa. Sirve para ver hacia qué lado manda la pieza a su caja.
    d 1 90     lo mismo, pero girando alrededor de 90 grados (útil si el reposo es 0 y no cabe un lado)
    c 2        ciclos de desvío de la compuerta 2: 3 veces reposo -> activo -> reposo
    t          secuencia: compuerta 1, luego 2, luego 3 (reposo -> activo -> reposo)
    1 70       compuerta 1 a 70 grados, a velocidad moderada (sirve con 1, 2 o 3)
    b 2        barrido de la compuerta 2: 0 -> 180 -> reposo
    v 40       velocidad en grados por segundo (20 lento, 60 moderado, 120 rápido)
    p 1 1500   compuerta 1 con un pulso exacto en microsegundos (500 a 2500), sin suavizado
    s          soltar todas          s 2   soltar solo la compuerta 2
    u          activar / desactivar el modo uno a uno
    ?          ver estado y ayuda
    q          salir (suelta todo)

Conexión de cada servo: café -> GND común (OUT- del XL4015 + GND del ESP32),
rojo -> 5.0-5.5 V del XL4015 (NUNCA del ESP32), naranja -> GPIO de la tabla PINES.
Cuando tengas los ángulos buenos, pásalos a REPOSO y ACTIVO de aquí y de main.py.
"""
import select
import sys
import time

from machine import PWM, Pin

PINES = (18, 19, 23)                # compuerta 1, 2 y 3
REPOSO = [0, 0, 0]                  # paleta paralela al borde: no estorba a las piezas
ACTIVO = [90, 90, 90]               # paleta en diagonal (30-45 grados respecto al flujo)
PULSO_MIN_US, PULSO_MAX_US = 500, 2400   # pulso para 0 y 180 grados
VELOCIDAD = 60                      # grados por segundo: moderada (90 grados en 1.5 s)
GIRO_DIRECCION = 45                 # grados que gira hacia cada lado en la prueba de dirección
PAUSA_S = 0.8                       # pausa en cada extremo de un movimiento

# duty_u16=0: arrancan sin pulso. (duty_ns=0 en el constructor falla en MicroPython 1.29: "PWM is inactive")
servos = [PWM(Pin(p), freq=50, duty_u16=0) for p in PINES]
angulo = [None, None, None]         # None = suelto (sin pulso)
pulso = [None, None, None]
ultimo = [None, None, None]         # último ángulo mandado; un servo suelto se queda casi donde estaba
uno_a_uno = True
velocidad = VELOCIDAD


def soltar(n=None):
    """Quita el pulso a la compuerta n, o a todas si n es None."""
    for i in (range(3) if n is None else [n - 1]):
        servos[i].duty_u16(0)
        angulo[i] = None
        pulso[i] = None


def _activar(n):
    if uno_a_uno:
        for i in (1, 2, 3):
            if i != n and pulso[i - 1] is not None:
                soltar(i)
                print("  (compuerta", i, "suelta)")


def mover_us(n, us):
    """Manda un pulso exacto (microsegundos) a la compuerta n."""
    if n not in (1, 2, 3):
        print("La compuerta debe ser 1, 2 o 3")
        return None
    us = max(500, min(2500, us))
    _activar(n)
    servos[n - 1].duty_ns(int(us * 1000))
    pulso[n - 1] = us
    return us


def _poner(n, grados):
    """Pone la compuerta n en 'grados' de inmediato (sin suavizado). Regresa el pulso o None."""
    us = PULSO_MIN_US + (PULSO_MAX_US - PULSO_MIN_US) * grados / 180
    if mover_us(n, us) is None:
        return None
    angulo[n - 1] = grados
    ultimo[n - 1] = grados
    return us


def ir(n, destino, avisar=True):
    """Lleva la compuerta n a 'destino' grados poco a poco, a 'velocidad' grados por segundo."""
    if n not in (1, 2, 3):
        print("La compuerta debe ser 1, 2 o 3")
        return
    destino = max(0, min(180, int(destino)))
    actual = angulo[n - 1] if angulo[n - 1] is not None else ultimo[n - 1]
    if actual is None:                       # primera vez: no se sabe dónde está, va directo
        _poner(n, destino)
        time.sleep_ms(500)
    else:
        paso = max(1, round(velocidad * 0.02))   # grados por cada periodo de 20 ms del servo
        espera = max(20, int(1000 * paso / velocidad))   # a menos de 50 grados/s espera más por paso
        while True:
            if abs(destino - actual) <= paso:
                actual = destino
            else:
                actual += paso if destino > actual else -paso
            _poner(n, actual)
            if actual == destino:
                break
            time.sleep_ms(espera)
    if avisar:
        us = PULSO_MIN_US + (PULSO_MAX_US - PULSO_MIN_US) * destino / 180
        print("compuerta", n, "| GPIO", PINES[n - 1], "|", destino, "grados |", int(us), "us",
              "| solo esta activa" if uno_a_uno else "")


def secuencia():
    for n in (1, 2, 3):
        print("--- compuerta", n, "---")
        ir(n, REPOSO[n - 1])
        time.sleep(PAUSA_S)
        ir(n, ACTIVO[n - 1])
        time.sleep(PAUSA_S * 1.5)
        ir(n, REPOSO[n - 1])
        time.sleep(PAUSA_S)
        if uno_a_uno:
            soltar(n)
    print("Secuencia terminada.")


def direccion(n, centro=None):
    """Desde el centro (reposo por defecto) gira hacia un lado (+) y hacia el otro (-) y regresa."""
    r = REPOSO[n - 1] if centro is None else max(0, min(180, centro))
    print("=== DIRECCION compuerta", n, "| centro", r, "grados | giro", GIRO_DIRECCION, "grados ===")
    ir(n, r)
    time.sleep(PAUSA_S)
    for signo, lado in ((1, "LADO A (angulo mayor)"), (-1, "LADO B (angulo menor)")):
        destino = r + signo * GIRO_DIRECCION
        if not 0 <= destino <= 180:
            print(lado, ": no cabe,", destino, "grados queda fuera de 0-180")
            continue
        print(lado, "->", destino, "grados")
        ir(n, destino, avisar=False)
        time.sleep(PAUSA_S)
        ir(n, r, avisar=False)
        time.sleep(PAUSA_S)
    print("Anota que lado empuja la pieza hacia su caja: ese es el lado de ACTIVO.")


def ciclos(n, veces=3):
    print("=== CICLOS compuerta", n, "| reposo", REPOSO[n - 1], "-> activo", ACTIVO[n - 1], "===")
    ir(n, REPOSO[n - 1], avisar=False)
    time.sleep(PAUSA_S)
    for i in range(veces):
        print("ciclo", i + 1, "de", veces)
        ir(n, ACTIVO[n - 1], avisar=False)
        time.sleep(PAUSA_S)
        ir(n, REPOSO[n - 1], avisar=False)
        time.sleep(PAUSA_S)
    print("Ciclos terminados.")


def barrido(n):
    ir(n, 0)
    time.sleep(PAUSA_S)
    ir(n, 180)
    time.sleep(PAUSA_S)
    ir(n, REPOSO[n - 1])


def ayuda():
    estado = []
    for i in range(3):
        if pulso[i] is None:
            estado.append("C%d suelta" % (i + 1))
        elif angulo[i] is None:
            estado.append("C%d %d us" % (i + 1, pulso[i]))
        else:
            estado.append("C%d %d grados" % (i + 1, angulo[i]))
    print("Estado:", " | ".join(estado), "| uno a uno:", "SI" if uno_a_uno else "NO",
          "| velocidad", velocidad, "grados/s")
    print("REPOSO", REPOSO, "| ACTIVO", ACTIVO)
    print("Comandos: d 1 / d 1 90 direccion | c 1 ciclos | t | 1 70 | b 2 | v 60 | p 1 1500 | s | s 2 | u | ? | q")


def atender(linea):
    """Regresa False cuando hay que salir."""
    global uno_a_uno, velocidad
    partes = linea.strip().lower().split()
    if not partes:
        return True
    c = partes[0]
    try:
        if c == "q":
            return False
        if c == "t":
            secuencia()
        elif c == "s" and len(partes) == 1:
            soltar()
            print("Todas sueltas (sin pulso)")
        elif c == "s" and len(partes) == 2:
            n = int(partes[1])
            if n in (1, 2, 3):
                soltar(n)
                print("Compuerta", n, "suelta")
            else:
                print("La compuerta debe ser 1, 2 o 3")
        elif c == "u":
            uno_a_uno = not uno_a_uno
            print("Modo uno a uno:", "SI (solo la ultima compuerta recibe pulso)" if uno_a_uno
                  else "NO (todas mantienen su posicion)")
        elif c == "v" and len(partes) == 2:
            velocidad = max(5, min(300, int(partes[1])))
            print("Velocidad:", velocidad, "grados/s")
        elif c == "?":
            ayuda()
        elif c == "d" and len(partes) == 3:
            n = int(partes[1])
            if n not in (1, 2, 3):
                print("La compuerta debe ser 1, 2 o 3")
            else:
                direccion(n, int(float(partes[2])))
        elif c in ("d", "c", "b") and len(partes) == 2:
            n = int(partes[1])
            if n not in (1, 2, 3):
                print("La compuerta debe ser 1, 2 o 3")
            else:
                {"d": direccion, "c": ciclos, "b": barrido}[c](n)
        elif c == "p" and len(partes) == 3:
            n = int(partes[1])
            us = mover_us(n, int(float(partes[2])))
            if us is not None:
                angulo[n - 1] = None
                ultimo[n - 1] = max(0, min(180, round((us - PULSO_MIN_US) * 180 / (PULSO_MAX_US - PULSO_MIN_US))))
                print("compuerta", n, "| GPIO", PINES[n - 1], "| pulso", int(us), "us")
        elif c in ("1", "2", "3") and len(partes) == 2:
            ir(int(c), int(float(partes[1])))
        else:
            print("Comando no reconocido:", linea.strip())
            ayuda()
    except ValueError:
        print("Numero no valido en:", linea.strip())
    return True


print("PRUEBA DE COMPUERTAS - ESP32 (uno a uno, velocidad", velocidad, "grados/s)")
print("No se mueve nada hasta que mandes un comando. Empieza con:  d 1")
ayuda()

entrada = select.poll()
entrada.register(sys.stdin, select.POLLIN)
buffer = ""
try:
    seguir = True
    while seguir:
        while entrada.poll(0):
            ch = sys.stdin.read(1)
            if ch in "\r\n":
                seguir = atender(buffer)
                buffer = ""
                if not seguir:
                    break
            else:
                buffer += ch
                if len(buffer) > 30:
                    buffer = ""
        time.sleep_ms(20)
finally:
    soltar()
    for s in servos:
        s.deinit()
    print("Fin de la prueba: servos sueltos")
