"""Agrupa extractos y genera el maestro único."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from config import SALIDA_CONSOLIDADO_DIR
from exportar_maestro import exportar_maestro
from fuentes_json import cargar_extractos
from metadatos import parse_fecha, slug


def _rango_fechas(transacciones: list[dict]) -> tuple[str | None, str | None]:
    fechas = [parse_fecha(t["fecha"]) for t in transacciones if t.get("fecha")]
    fechas = [f for f in fechas if f]
    if not fechas:
        return None, None
    fechas.sort()
    return fechas[0].strftime("%d/%m/%Y"), fechas[-1].strftime("%d/%m/%Y")


def _ordenar(transacciones: list[dict]) -> list[dict]:
    def key(t: dict):
        f = parse_fecha(t.get("fecha", ""))
        return (f or datetime.min, t.get("descripcion", ""))

    return sorted(transacciones, key=key)


def consolidar() -> dict:
    por_entidad: dict[str, dict] = {}
    por_mes: dict[str, list[dict]] = defaultdict(list)
    indice_entidades: list[dict] = []

    for ruta_json, datos in cargar_extractos():
        eid = datos.get("id_entidad") or "desconocido"
        mes = datos.get("mes_archivo") or ruta_json.parent.name

        if eid not in por_entidad:
            por_entidad[eid] = {
                "id": eid,
                "entidad": datos.get("entidad", "Desconocido"),
                "productos": [],
                "numero_cuenta": datos.get("numero_cuenta"),
                "titular": datos.get("titular"),
                "archivos": [],
                "transacciones": [],
            }

        ent = por_entidad[eid]
        if datos.get("producto") and datos["producto"] not in ent["productos"]:
            ent["productos"].append(datos["producto"])
        if datos.get("titular") and not ent.get("titular"):
            ent["titular"] = datos["titular"]
        ent["archivos"].append(datos.get("archivo_origen", ruta_json.name))
        ent["transacciones"].extend(datos.get("transacciones", []))

        for t in datos.get("transacciones", []):
            por_mes[mes].append({**t, "id_entidad": eid})

    for ent in por_entidad.values():
        ent["transacciones"] = _ordenar(ent["transacciones"])
        ent["archivos"] = sorted(set(ent["archivos"]))
        desde, hasta = _rango_fechas(ent["transacciones"])
        ent["periodo_desde"] = desde
        ent["periodo_hasta"] = hasta
        ent["total_movimientos"] = len(ent["transacciones"])
        indice_entidades.append(
            {
                "id": ent["id"],
                "entidad": ent["entidad"],
                "productos": ent.get("productos") or [],
                "numero_cuenta": ent.get("numero_cuenta"),
                "extractos": len(ent["archivos"]),
                "movimientos": ent["total_movimientos"],
                "periodo_desde": desde,
                "periodo_hasta": hasta,
            }
        )

    indice_entidades.sort(key=lambda x: (x["entidad"], x.get("numero_cuenta") or ""))
    por_mes_dict = {mes: _ordenar(movs) for mes, movs in sorted(por_mes.items())}

    dest = SALIDA_CONSOLIDADO_DIR
    dest.mkdir(parents=True, exist_ok=True)

    (dest / "indice.json").write_text(
        json.dumps({"entidades": indice_entidades}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (dest / "por_mes.json").write_text(
        json.dumps(por_mes_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ent_dir = dest / "entidades"
    ent_dir.mkdir(exist_ok=True)
    for eid, ent in por_entidad.items():
        (ent_dir / f"{slug(eid)}.json").write_text(
            json.dumps(ent, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    maestro = exportar_maestro(dest)
    return {
        "entidades": indice_entidades,
        "por_entidad": por_entidad,
        "por_mes": por_mes_dict,
        "maestro": maestro,
    }


if __name__ == "__main__":
    resumen = consolidar()
    m = resumen["maestro"]
    print(f"Maestro: {m['total_movimientos']} movimientos → salida/consolidado/maestro.xlsx")
    print(f"  Años gravables: {', '.join(str(a) for a in m['anios_gravables'])}")
    print(f"  Entidades (columna filtro): {', '.join(m['entidades'])}")
