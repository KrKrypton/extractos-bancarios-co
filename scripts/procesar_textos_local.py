#!/usr/bin/env python3
"""Procesa salida/texto → salida/json + salida/md (sin Ollama)."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import SALIDA_JSON_DIR, SALIDA_TEXTO_DIR
from consolidar import consolidar
from markdown_export import generar_tabla_markdown, ruta_md_desde_texto
from procesador_ollama import ruta_json_salida
from procesador_texto import procesar_archivo_texto


def main() -> None:
    parser = argparse.ArgumentParser(description="Estructura extractos .txt localmente.")
    parser.add_argument("--mes", help="Solo carpeta YYYY-MM")
    parser.add_argument("--texto", help="Un .txt específico")
    parser.add_argument("--pendientes", action="store_true", help="Solo sin JSON")
    args = parser.parse_args()

    if args.texto:
        archivos = [Path(args.texto)]
    elif args.mes:
        archivos = sorted((SALIDA_TEXTO_DIR / args.mes).glob("*.txt"))
    else:
        archivos = sorted(SALIDA_TEXTO_DIR.rglob("*.txt"))

    if args.pendientes:
        archivos = [t for t in archivos if not ruta_json_salida(t).exists()]

    if not archivos:
        print("No hay archivos para procesar.")
        return

    ok, fallidos = 0, []
    for txt in archivos:
        try:
            datos = procesar_archivo_texto(txt)
            if "banco" not in datos:
                fallidos.append(txt.name)
                print(f"[SKIP] Sin banco: {txt.name}")
                continue

            ruta_json = ruta_json_salida(txt)
            ruta_json.parent.mkdir(parents=True, exist_ok=True)
            ruta_json.write_text(
                json.dumps(datos, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            generar_tabla_markdown(datos, ruta_md_desde_texto(txt))
            n = len(datos.get("transacciones", []))
            print(f"[OK] {txt.name} ({n} movimientos)")
            ok += 1
        except Exception as e:
            fallidos.append(txt.name)
            print(f"[SKIP] {txt.name}: {e}")

    print(f"\nListo: {ok}/{len(archivos)}")
    if fallidos:
        print(f"Omitidos ({len(fallidos)}): {', '.join(fallidos)}")

    print("\nConsolidando maestro...")
    resumen = consolidar()
    m = resumen["maestro"]
    print(f"  {m['total_movimientos']} movimientos → salida/consolidado/maestro.xlsx")


if __name__ == "__main__":
    main()
