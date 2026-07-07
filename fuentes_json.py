"""Carga extractos JSON expandidos por cuenta."""

from __future__ import annotations

import json
from pathlib import Path

from config import SALIDA_JSON_DIR
from metadatos import expandir_cuentas


def cargar_extractos() -> list[tuple[Path, dict]]:
    items: list[tuple[Path, dict]] = []
    for ruta in sorted(SALIDA_JSON_DIR.rglob("*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        for expandido in expandir_cuentas(datos):
            items.append((ruta, expandido))
    return items
