#!/usr/bin/env python3
"""Lista .txt en salida/texto sin .json correspondiente en salida/json."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import SALIDA_JSON_DIR, SALIDA_TEXTO_DIR


def json_para(txt: Path) -> Path:
    rel = txt.relative_to(SALIDA_TEXTO_DIR)
    return SALIDA_JSON_DIR / rel.with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mes", help="Filtrar carpeta YYYY-MM")
    parser.add_argument("--contar", action="store_true", help="Solo imprimir cantidad")
    args = parser.parse_args()

    if args.mes:
        textos = sorted((SALIDA_TEXTO_DIR / args.mes).glob("*.txt"))
    else:
        textos = sorted(SALIDA_TEXTO_DIR.rglob("*.txt"))

    pendientes = [t for t in textos if not json_para(t).exists()]

    if args.contar:
        print(len(pendientes))
        return

    for txt in pendientes:
        print(txt.relative_to(SALIDA_TEXTO_DIR))


if __name__ == "__main__":
    main()
