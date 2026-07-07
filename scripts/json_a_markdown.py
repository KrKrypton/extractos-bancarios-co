#!/usr/bin/env python3
"""Genera tablas Markdown desde JSON ya estructurado (sin Ollama)."""

import argparse
import json
from pathlib import Path

from config import SALIDA_JSON_DIR
from markdown_export import generar_tabla_markdown, ruta_md_desde_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte salida/json/*.json en tablas salida/md/*.md"
    )
    parser.add_argument("--mes", help="Solo carpeta YYYY-MM")
    parser.add_argument("--json", help="Un archivo .json específico")
    parser.add_argument(
        "--pendientes",
        action="store_true",
        help="Solo JSON sin .md correspondiente",
    )
    args = parser.parse_args()

    if args.json:
        archivos = [Path(args.json)]
    elif args.mes:
        archivos = sorted((SALIDA_JSON_DIR / args.mes).glob("*.json"))
    else:
        archivos = sorted(SALIDA_JSON_DIR.rglob("*.json"))

    if args.pendientes:
        archivos = [j for j in archivos if not ruta_md_desde_json(j).exists()]

    if not archivos:
        print("No hay archivos JSON para convertir.")
        return

    ok = 0
    for ruta_json in archivos:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
        ruta_md = ruta_md_desde_json(ruta_json)
        if generar_tabla_markdown(datos, ruta_md):
            ok += 1
            print(f"[OK] {ruta_md.relative_to(ruta_md.parent.parent)}")

    print(f"\nListo: {ok}/{len(archivos)} tablas Markdown.")


if __name__ == "__main__":
    main()
