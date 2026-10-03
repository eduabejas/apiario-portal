#!/usr/bin/env python3
"""Genera un informe real (sin enviarlo) con las fuentes en vivo, para una
visita de prueba de mañana 09:00–13:00, y mide cuánto tarda cada parte.

Uso (desde interfaz4/):
    uv run python scripts/informe_en_vivo.py [--salida tests/fixtures/ultima_verificacion]
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import timedelta
from pathlib import Path

from interfaz4 import tiempo
from interfaz4.config import cargar_config
from interfaz4.informe.constructor import generar
from interfaz4.informe.recoleccion import construir_recolector, recolectar
from interfaz4.modelos import Visita

BASE = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=str(BASE / "tests" / "fixtures" / "ultima_verificacion"))
    ap.add_argument("--hito", type=int, default=24)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = cargar_config(BASE)
    ahora = tiempo.ahora()
    manana = (ahora + timedelta(days=1)).date()
    visita = Visita(
        id="prueba-en-vivo",
        apiario=next(iter(config.apiarios)),
        fecha=manana,
        desde="09:00",
        hasta="13:00",
        responsable="Prueba automática",
        notas="Informe de verificación (no se envía)",
    )
    recolector = construir_recolector(config)
    t0 = time.time()
    tiempos = {}
    for nombre in list(recolector.fuentes):
        t = time.time()
        recolector.serie(nombre, config.apiario(visita.apiario), tiempo.piso_hora(visita.inicio), tiempo.techo_hora(visita.fin), "todas")
        tiempos[nombre] = time.time() - t
    datos = recolectar(config, visita, args.hito, ahora, recolector)
    total = time.time() - t0
    render = generar(datos)
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "informe_en_vivo.html").write_text(render.html, encoding="utf-8")
    (salida / "informe_en_vivo.txt").write_text(render.texto, encoding="utf-8")
    lineas = [
        f"Informe en vivo ({args.hito} h) para {tiempo.fmt_dia_fecha(visita.fecha)} 09:00–13:00, generado {tiempo.fmt_momento(ahora)}",
        f"Tiempo total de recolección: {total:.1f} s; por fuente (ventana): "
        + ", ".join(f"{k} {v:.1f} s" for k, v in tiempos.items()),
        f"Tramo previo: {datos.tramo_desde} → {datos.tramo_hasta}",
        "Errores/avisos: " + ("; ".join(e for s in [*datos.series, *datos.series_previas] for e in s.errores) or "ninguno"),
        f"Alertas: disponible={datos.alertas.disponible if datos.alertas else 'deshabilitada'}, "
        f"cantidad={len(datos.alertas.alertas) if datos.alertas else 0}",
    ]
    texto = "\n".join(lineas)
    print(texto)
    print(render.texto)
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write("\n## Informe en vivo\n\n```\n" + texto + "\n\n" + render.texto + "\n```\n")


if __name__ == "__main__":
    main()
