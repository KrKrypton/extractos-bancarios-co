"""Exporta un maestro único: todas las transacciones, entidad como columna."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, SALIDA_CONSOLIDADO_DIR
from fuentes_json import cargar_extractos
from maestro_workbook import generar_maestro_workbook
from metadatos import parse_fecha

COLUMNAS = [
    "anio_gravable",
    "fecha",
    "entidad",
    "numero_cuenta",
    "producto",
    "tipo",
    "monto",
    "descripcion",
    "origen",
]


def _anio_gravable(fecha: str, mes_archivo: str | None) -> int | None:
    f = parse_fecha(fecha)
    if f:
        return f.year
    if mes_archivo and len(mes_archivo) >= 4:
        try:
            return int(mes_archivo[:4])
        except ValueError:
            pass
    return None


def _fila_maestro(datos: dict, t: dict) -> dict:
    mes = datos.get("mes_archivo")
    fecha = t.get("fecha", "")
    return {
        "anio_gravable": _anio_gravable(fecha, mes),
        "fecha": fecha,
        "entidad": t.get("entidad") or datos.get("entidad", ""),
        "numero_cuenta": t.get("numero_cuenta") or datos.get("numero_cuenta") or "",
        "producto": t.get("producto") or datos.get("producto") or "",
        "tipo": t.get("tipo", ""),
        "monto": t.get("monto", 0),
        "descripcion": t.get("descripcion", ""),
        "origen": t.get("origen", datos.get("archivo_origen", "")),
    }


def _clave_dedup(fila: dict) -> tuple:
    return (
        fila["entidad"],
        fila["numero_cuenta"],
        fila["fecha"],
        fila["descripcion"],
        fila["tipo"],
        round(float(fila["monto"]), 2),
    )


def construir_maestro(dedup: bool = True) -> list[dict]:
    filas: list[dict] = []
    vistos: set[tuple] = set()

    for _ruta, datos in cargar_extractos():
        for t in datos.get("transacciones", []):
            fila = _fila_maestro(datos, t)
            if dedup:
                clave = _clave_dedup(fila)
                if clave in vistos:
                    continue
                vistos.add(clave)
            filas.append(fila)

    def sort_key(f: dict):
        fdt = parse_fecha(f.get("fecha", ""))
        return (
            f.get("anio_gravable") or 0,
            fdt or datetime.min,
            f.get("entidad", ""),
            f.get("descripcion", ""),
        )

    return sorted(filas, key=sort_key)


def _escribir_csv(filas: list[dict], ruta: Path) -> None:
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)


def _escribir_xlsx(filas: list[dict], ruta: Path) -> None:
    generar_maestro_workbook(filas, ruta)


def exportar_maestro(destino: Path = SALIDA_CONSOLIDADO_DIR, dedup: bool = True) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    filas = construir_maestro(dedup=dedup)

    ruta_csv = destino / "maestro.csv"
    ruta_json = destino / "maestro.json"
    ruta_xlsx = destino / "maestro.xlsx"
    ruta_principal = BASE_DIR / "Maestro_Movimientos_Bancarios.xlsx"

    _escribir_csv(filas, ruta_csv)
    ruta_json.write_text(
        json.dumps(filas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _escribir_xlsx(filas, ruta_xlsx)
    _escribir_xlsx(filas, ruta_principal)

    anios = sorted({f["anio_gravable"] for f in filas if f.get("anio_gravable")})
    entidades = sorted({f["entidad"] for f in filas if f.get("entidad")})

    resumen = {
        "total_movimientos": len(filas),
        "anios_gravables": anios,
        "entidades": entidades,
        "archivos": {
            "csv": str(ruta_csv),
            "json": str(ruta_json),
            "xlsx": str(ruta_xlsx),
            "xlsx_principal": str(ruta_principal),
        },
    }
    (destino / "maestro_resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return resumen


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Exporta maestro único de transacciones.")
    parser.add_argument("--sin-dedup", action="store_true", help="No eliminar duplicados")
    args = parser.parse_args()

    r = exportar_maestro(dedup=not args.sin_dedup)
    print(f"Maestro: {r['total_movimientos']} movimientos")
    print(f"  Años: {', '.join(str(a) for a in r['anios_gravables'])}")
    print(f"  Entidades: {', '.join(r['entidades'])}")
    print(f"  → {r['archivos']['xlsx']}")
    print(f"  → {r['archivos']['xlsx_principal']}")
