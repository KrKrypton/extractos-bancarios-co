"""Genera una vista Markdown filtrada por entidad y/o fechas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import SALIDA_CONSOLIDADO_DIR
from markdown_export import generar_tabla_markdown
from metadatos import parse_fecha


def cargar_indice() -> list[dict]:
    ruta = SALIDA_CONSOLIDADO_DIR / "indice.json"
    if not ruta.exists():
        raise SystemExit("Ejecuta primero: .venv/bin/python consolidar.py")
    return json.loads(ruta.read_text(encoding="utf-8"))["entidades"]


def cargar_entidad(eid: str) -> dict:
    from metadatos import slug

    ruta = SALIDA_CONSOLIDADO_DIR / "entidades" / f"{slug(eid)}.json"
    if not ruta.exists():
        raise SystemExit(f"No existe entidad: {eid}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def filtrar_transacciones(
    transacciones: list[dict],
    desde: str | None,
    hasta: str | None,
    mes: str | None,
) -> list[dict]:
    resultado = []
    d0 = parse_fecha(desde) if desde else None
    d1 = parse_fecha(hasta) if hasta else None

    for t in transacciones:
        f = parse_fecha(t.get("fecha", ""))
        if mes:
            if not f or f.strftime("%Y-%m") != mes:
                continue
        if d0 and f and f < d0:
            continue
        if d1 and f and f > d1:
            continue
        resultado.append(t)
    return resultado


def listar_entidades() -> None:
    for e in cargar_indice():
        prods = ", ".join(e["productos"]) if e.get("productos") else ""
        prod = f" · {prods}" if prods else ""
        cuenta = f" · {e['numero_cuenta']}" if e.get("numero_cuenta") else ""
        print(
            f"{e['id']}\n"
            f"  {e['entidad']}{prod}{cuenta} — "
            f"{e['movimientos']} mov. ({e.get('periodo_desde')} → {e.get('periodo_hasta')})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Vista consolidada filtrable.")
    parser.add_argument("--listar", action="store_true", help="Lista entidades disponibles")
    parser.add_argument("--entidad", help="Nombre parcial: Nequi, Bancolombia, Nu...")
    parser.add_argument("--id", dest="eid", help="ID exacto de entidad")
    parser.add_argument("--mes", help="Filtrar YYYY-MM")
    parser.add_argument("--desde", help="Fecha desde DD/MM/YYYY")
    parser.add_argument("--hasta", help="Fecha hasta DD/MM/YYYY")
    parser.add_argument("-o", "--salida", help="Archivo .md de salida")
    args = parser.parse_args()

    if args.listar:
        listar_entidades()
        return

    indice = cargar_indice()
    if args.eid:
        candidatos = [e for e in indice if e["id"] == args.eid]
    elif args.entidad:
        q = args.entidad.lower()
        candidatos = [e for e in indice if q in e["entidad"].lower() or q in e["id"]]
    else:
        parser.error("Indica --entidad, --id o --listar")

    if not candidatos:
        raise SystemExit("Ninguna entidad coincide.")

    if len(candidatos) > 1 and not args.eid:
        print("Varias entidades coinciden. Usa --id con uno de estos:")
        for e in candidatos:
            print(f"  {e['id']}")
        return

    ent_meta = candidatos[0]
    ent = cargar_entidad(ent_meta["id"])
    movs = filtrar_transacciones(ent["transacciones"], args.desde, args.hasta, args.mes)

    titulo = ent_meta["entidad"]
    if ent_meta.get("productos"):
        titulo += f" — {', '.join(ent_meta['productos'])}"
    elif ent.get("productos"):
        titulo += f" — {', '.join(ent['productos'])}"
    if ent_meta.get("numero_cuenta"):
        titulo += f" ({ent_meta['numero_cuenta']})"

    datos = {"banco": titulo, "transacciones": movs}
    salida = Path(args.salida) if args.salida else (
        SALIDA_CONSOLIDADO_DIR / f"vista_{ent_meta['id'].replace(':', '_')}.md"
    )
    generar_tabla_markdown(datos, salida)
    print(f"Vista generada: {salida} ({len(movs)} movimientos)")


if __name__ == "__main__":
    main()
