"""Metadatos normalizados para agrupar y filtrar extractos."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from config import SALIDA_JSON_DIR, SALIDA_TEXTO_DIR


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def parse_fecha(fecha: str) -> datetime | None:
    fecha = fecha.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha, fmt)
        except ValueError:
            continue
    return None


def inferir_desde_nombre(nombre: str) -> dict:
    n = nombre.lower()
    meta: dict = {}

    if "cuentanu" in n:
        meta.update(entidad="Nu", producto="Cuenta Nu")
    elif "pensionesobligatorias" in n:
        meta.update(entidad="Protección", producto="Pensiones obligatorias")
    elif "extracto_cuenta" in n:
        meta.update(entidad="Nequi", producto="Cuenta de ahorro")
    elif "estado_cuenta" in n or "extracto_20" in n and re.search(r"extracto_\d{4}-\d{2}-\d{2}", n):
        meta.update(entidad="RappiPay", producto="RappiCuenta")
    elif "bfco" in n or "banco falabella" in n:
        meta.update(entidad="Banco Falabella")
    elif "tarjeta_mastercard" in n:
        meta.update(entidad="Bancolombia", producto="Tarjeta Mastercard")
    elif "cta_ahorros" in n:
        meta.update(entidad="Bancolombia", producto="Cuenta de ahorros")
    elif "credito" in n:
        meta.update(entidad="Bancolombia", producto="Crédito")
    elif "consolidado" in n or "comisiones" in n:
        meta.update(entidad="Bancolombia", producto="Consolidado / comisiones")
    elif "extracto_" in n and re.search(r"extracto_\d{6}_", n):
        meta.update(entidad="Bancolombia")

    m = re.search(r"(\d{12})", nombre)
    if m and "numero_cuenta" not in meta:
        meta.setdefault("numero_cuenta", m.group(1))

    return meta


def entidad_id(datos: dict) -> str:
    """Clave única: entidad + número de cuenta (sin duplicar por producto/página)."""
    entidad = datos.get("entidad") or datos.get("banco", "Desconocido")
    cuenta = datos.get("numero_cuenta") or "general"
    return f"{slug(entidad)}:{cuenta}"


def enriquecer(datos: dict, ruta_txt: Path) -> dict:
    """Añade metadatos estándar y origen en cada transacción."""
    rel_txt = ruta_txt.resolve().relative_to(SALIDA_TEXTO_DIR.resolve())
    mes_archivo = rel_txt.parts[0] if len(rel_txt.parts) > 1 else None
    inferidos = inferir_desde_nombre(ruta_txt.name)

    if "entidad" not in datos and "banco" in datos:
        datos["entidad"] = datos["banco"]
    datos.setdefault("entidad", inferidos.get("entidad", "Desconocido"))
    datos.setdefault("banco", datos["entidad"])
    for k, v in inferidos.items():
        datos.setdefault(k, v)

    datos["archivo_origen"] = str(rel_txt)
    if mes_archivo:
        datos["mes_archivo"] = mes_archivo
    datos["id_entidad"] = entidad_id(datos)

    origen = str(rel_txt.with_suffix(".json"))
    for t in datos.get("transacciones", []):
        t.setdefault("origen", origen)
        t.setdefault("entidad", datos["entidad"])
        if datos.get("numero_cuenta"):
            t.setdefault("numero_cuenta", datos["numero_cuenta"])
        if datos.get("producto"):
            t.setdefault("producto", datos["producto"])

    return datos


def expandir_cuentas(datos: dict) -> list[dict]:
    """Un JSON con varias cuentas (ej. Falabella) → una entrada por cuenta."""
    if not datos.get("cuentas"):
        return [datos]

    base = {k: v for k, v in datos.items() if k != "cuentas"}
    resultado = []
    for cuenta in datos["cuentas"]:
        item = {**base, **cuenta}
        item["transacciones"] = cuenta.get("transacciones", [])
        item["id_entidad"] = entidad_id(item)
        for t in item["transacciones"]:
            t.setdefault("origen", datos.get("archivo_origen", "").replace(".txt", ".json"))
            t.setdefault("entidad", item["entidad"])
            if item.get("numero_cuenta"):
                t.setdefault("numero_cuenta", item["numero_cuenta"])
            if item.get("producto"):
                t.setdefault("producto", item["producto"])
        resultado.append(item)
    return resultado
