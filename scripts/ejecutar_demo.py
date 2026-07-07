#!/usr/bin/env python3
"""Demo con ejemplos sintéticos (sin PDFs ni datos reales)."""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import SALIDA_CONSOLIDADO_DIR, SALIDA_JSON_DIR, SALIDA_TEXTO_DIR
from exportar_maestro import exportar_maestro
from markdown_export import generar_tabla_markdown, ruta_md_desde_texto
from procesador_ollama import ruta_json_salida
from procesador_texto import procesar_archivo_texto

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos" / "texto"
DESTINO = SALIDA_TEXTO_DIR / "demo"


def main() -> None:
    if not EJEMPLOS.is_dir():
        print(f"No hay ejemplos en {EJEMPLOS}")
        return

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)

    total_mov = 0
    for ejemplo in sorted(EJEMPLOS.glob("*.txt")):
        destino_txt = DESTINO / ejemplo.name
        shutil.copy2(ejemplo, destino_txt)
        datos = procesar_archivo_texto(destino_txt)
        n = len(datos.get("transacciones", []))
        entidad = datos.get("entidad", "?")
        print(f"[OK] {ejemplo.name}: {entidad}, {n} movimientos")

        ruta_json = ruta_json_salida(destino_txt)
        ruta_json.parent.mkdir(parents=True, exist_ok=True)
        ruta_json.write_text(
            json.dumps(datos, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        generar_tabla_markdown(datos, ruta_md_desde_texto(destino_txt))
        total_mov += n

    resumen = exportar_maestro()
    print(f"\nDemo listo: {total_mov} movimientos en ejemplos")
    print(f"  JSON → {SALIDA_JSON_DIR / 'demo'}")
    print(f"  Maestro → {SALIDA_CONSOLIDADO_DIR / 'maestro.xlsx'}")
    print(f"  Total maestro: {resumen['total_movimientos']} movimientos")


if __name__ == "__main__":
    main()
