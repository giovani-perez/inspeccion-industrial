"""Seguimiento de piezas entre cuadros y decisión por votación.

Cada pieza que se mueve por la banda se sigue cuadro a cuadro por su centroide. En cada cuadro
la forma detectada suma un voto. Cuando el centroide cruza la línea de decisión, la pieza se
decide UNA sola vez: la forma con más votos, si alcanza la confianza mínima; si no, rechazo.
Así la base de datos y el ESP32 reciben una decisión por pieza, no una por cuadro.
"""
from collections import Counter

SALIDA = {"circulo": 1, "cuadrado": 2, "triangulo": 3, "rechazo": 4}


class Decision:
    def __init__(self, id_pieza, clase, confianza, votos, cx, cy):
        self.id = id_pieza
        self.clase = clase
        self.salida = SALIDA[clase]
        self.confianza = confianza
        self.votos = votos
        self.cx, self.cy = cx, cy

    def __repr__(self):
        return f"Decision(id={self.id}, clase={self.clase}, salida={self.salida}, conf={self.confianza:.2f})"


class _Pista:
    def __init__(self, id_pieza, cx, cy):
        self.id = id_pieza
        self.cx, self.cy = cx, cy
        self.votos = Counter()
        self.perdidos = 0
        self.decidida = False


class Seguidor:
    """linea_x: coordenada x (px) de la línea de decisión. sentido: +1 si la banda mueve las piezas
    hacia x creciente en la imagen, -1 si hacia x decreciente."""

    def __init__(self, linea_x, sentido=1, dist_max=80, cuadros_perdida=8,
                 votos_min=5, confianza_min=0.70, primer_id=1):
        self.linea_x = linea_x
        self.sentido = 1 if sentido >= 0 else -1
        self.dist_max = dist_max
        self.cuadros_perdida = cuadros_perdida
        self.votos_min = votos_min
        self.confianza_min = confianza_min
        self.siguiente_id = primer_id
        self.pistas = []

    def _lado(self, cx):
        """Negativo antes de la línea, cero o positivo después."""
        return self.sentido * (cx - self.linea_x)

    def actualizar(self, detecciones):
        """detecciones: lista de (clase, cx, cy) del cuadro actual. Regresa las decisiones nuevas."""
        libres = list(range(len(detecciones)))
        pares = []
        for pista in self.pistas:
            for j in libres:
                _, cx, cy = detecciones[j]
                d = ((cx - pista.cx) ** 2 + (cy - pista.cy) ** 2) ** 0.5
                if d <= self.dist_max:
                    pares.append((d, pista, j))
        pares.sort(key=lambda p: p[0])
        usadas, asignadas = set(), set()
        decisiones = []
        for _, pista, j in pares:
            if pista.id in usadas or j in asignadas:
                continue
            usadas.add(pista.id)
            asignadas.add(j)
            clase, cx, cy = detecciones[j]
            antes = self._lado(pista.cx)
            pista.cx, pista.cy = cx, cy
            pista.perdidos = 0
            if not pista.decidida:
                if antes < 0 <= self._lado(cx):
                    pista.votos[clase] += 1
                    decisiones.append(self._decidir(pista))
                elif self._lado(cx) < 0:
                    pista.votos[clase] += 1
        for pista in self.pistas:
            if pista.id not in usadas:
                pista.perdidos += 1
        self.pistas = [p for p in self.pistas if p.perdidos <= self.cuadros_perdida]
        for j, (clase, cx, cy) in enumerate(detecciones):
            if j in asignadas:
                continue
            pista = _Pista(self.siguiente_id, cx, cy)
            self.siguiente_id += 1
            if self._lado(cx) < 0:
                pista.votos[clase] += 1
            else:
                pista.decidida = True      # apareció ya pasada la línea: no se decide dos veces
            self.pistas.append(pista)
        return decisiones

    def _decidir(self, pista):
        pista.decidida = True
        total = sum(pista.votos.values())
        clase, n = pista.votos.most_common(1)[0]
        confianza = n / total
        if total < self.votos_min or (clase != "rechazo" and confianza < self.confianza_min):
            clase = "rechazo"
        return Decision(pista.id, clase, confianza, dict(pista.votos), pista.cx, pista.cy)
