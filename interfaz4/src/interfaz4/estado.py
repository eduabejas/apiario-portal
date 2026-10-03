"""Estado de envíos (state/envios.json): idempotencia de los hitos."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from interfaz4 import tiempo
from interfaz4.modelos import RegistroHito


class EstadoEnvios:
    """{visita_id: {"24": {...}, "12": {...}}} con escritura atómica."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        self.datos: dict[str, dict[str, RegistroHito]] = {}
        if ruta.exists():
            crudo = json.loads(ruta.read_text(encoding="utf-8") or "{}")
            self.datos = {
                vid: {h: RegistroHito.model_validate(r) for h, r in (hitos or {}).items()} for vid, hitos in crudo.items()
            }

    def hito(self, visita_id: str, horas: int) -> RegistroHito:
        return self.datos.get(visita_id, {}).get(str(horas)) or RegistroHito()

    def actualizar(self, visita_id: str, horas: int, registro: RegistroHito) -> None:
        self.datos.setdefault(visita_id, {})[str(horas)] = registro

    def asegurar(self, visita_id: str, hitos: list[int]) -> None:
        """Deja los hitos 'pendiente' explícitos (como en la spec)."""
        for h in hitos:
            self.datos.setdefault(visita_id, {}).setdefault(str(h), RegistroHito())

    def como_dict(self) -> dict:
        def registro(r: RegistroHito) -> dict:
            d: dict = {"estado": r.estado}
            if r.momento:
                d["momento"] = tiempo.a_local(r.momento).isoformat(timespec="seconds")
            if r.canales:
                d["canales"] = dict(sorted(r.canales.items()))
            if r.snapshot:
                d["snapshot"] = r.snapshot
            if r.detalle:
                d["detalle"] = r.detalle
            return d

        return {
            vid: {h: registro(r) for h, r in sorted(hitos.items(), key=lambda kv: -int(kv[0]))}
            for vid, hitos in sorted(self.datos.items())
        }

    def guardar(self) -> bool:
        """Escribe solo si cambió. Devuelve True si hubo cambios."""
        nuevo = json.dumps(self.como_dict(), ensure_ascii=False, indent=2) + "\n"
        if self.ruta.exists() and self.ruta.read_text(encoding="utf-8") == nuevo:
            return False
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(".json.tmp")
        temporal.write_text(nuevo, encoding="utf-8")
        temporal.replace(self.ruta)
        return True


def momento_hito(inicio: datetime, horas: int) -> datetime:
    return tiempo.sumar_horas(inicio, -horas)
