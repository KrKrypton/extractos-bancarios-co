#!/usr/bin/env python3
"""Detecta y elimina documentos duplicados (PDF, texto, JSON, MD)."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from duplicados import eliminar_duplicados, guardar_informe


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filtra y borra extractos duplicados por contenido."
    )
    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Borrar archivos (por defecto solo muestra el informe)",
    )
    parser.add_argument(
        "--reporte",
        type=Path,
        help="Ruta del informe JSON (por defecto: salida/consolidado/duplicados_reporte.json)",
    )
    args = parser.parse_args()

    informe = eliminar_duplicados(ejecutar=args.ejecutar)
    ruta_reporte = guardar_informe(informe, args.reporte)
    print(f"\nInforme guardado en: {ruta_reporte}")


if __name__ == "__main__":
    main()
