"""Parsea textos crudos de extractos bancarios colombianos a JSON estructurado."""

from __future__ import annotations

import re
from pathlib import Path

from metadatos import enriquecer

DATE_FULL = re.compile(r"^\d{2}/\d{2}/\d{4}$")
AMOUNT_CO = re.compile(r"^-?[\d.]+,\d{2}$")
NEQUI_LINE = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$([+-]?[\d,]+\.\d{2})\s+\$"
)
BCO_CUENTA_LINE = re.compile(
    r"^(\d{1,2}/\d{1,2})\s+(.+?)\s+(-?[\d.,]+)\s+(-?[\d.,]+)$"
)
BCO_TARJETA_LINE = re.compile(
    r"^(?:[A-Z0-9]+\s+)?(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d.,]+)"
)
BCO_CREDITO_LINE = re.compile(
    r"^(ABONO A CAPITAL|INTER[EÉ]S CORRIENTE|INTER[EÉ]S MORA|SEGURO VIDA|OTROS CONCEPTOS|COMISI[OÓ]N FNG/FAG|IVA FNG/FAG|TOTAL)\s+([\d.,]+)(?:\s+([\d.,]+))?$",
    re.I,
)
BOGOTA_MOV_START = re.compile(r"^(\d{2}/\d{2})\s+(\d{4})\s*(.*)$")
BOGOTA_AMOUNTS = re.compile(r"([-]?[\d,]+\.\d{2})\s+([-]?[\d,]+\.\d{2})\s*$")
COOP_CONCEPTO = re.compile(r"^(.+?)\s+\$([\d.,]+)\s*$")
COOP_CONCEPTO_COD = re.compile(r"^(\d+)\s+(.+?)\s+\$([\d.,]+)")
ADDI_PAGO_MIN = re.compile(
    r"(?:Tu pago m[ií]nimo|Pago m[ií]nimo del mes|Pago m[ií]nimo a realizar)[:\s]*\$?\s*([\d.,\s]+)",
    re.I,
)
ADDI_FECHA = re.compile(
    r"(?:Fecha generaci[oó]n extracto|generado el|Extracto de \w+)\s*[:\s]*(\d{1,2})[/\s](\w+)[./\s]*(\d{4})",
    re.I,
)
BCO_CONSOLIDADO_LINE = re.compile(
    r"^(.+?)\s+(\d+)\s+COP\s+([\d.,]+)$"
)
NU_MESES = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}
MESES_TEXTO = {
    **NU_MESES,
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
NU_MOV_LINE = re.compile(
    r"^(\d{1,2})\s+([a-z]{3})\s+(.+?)\s+([+-])\$([\d.,]+)$",
    re.I,
)
NU_GMF_LINE = re.compile(
    r"^Impuesto del 4x1000\s+([+-])\$([\d.,]+)$",
    re.I,
)
NU_REND_LINE = re.compile(
    r"^Rendimiento total de tu cuenta\s+\+?\$([\d.,]+)$",
    re.I,
)
NU_PERIOD_LINE = re.compile(
    r"(\d{1,2})\s*-\s*(\d{1,2})\s+([A-ZÁÉÍÓÚÑa-z]{3})\s+(\d{4})",
    re.I,
)


def parse_money_token(value: str) -> float:
    value = value.strip()
    if value.count(",") == 1 and value.count(".") == 0:
        return float(value.replace(",", "."))
    return float(value.replace(",", ""))


def parse_col_amount(value: str) -> float:
    value = value.strip().replace(".", "").replace(",", ".")
    return float(value)


def parse_us_amount(value: str) -> float:
    return float(value.strip().replace(",", ""))


def _fecha_desde_texto(dia: str, mes_txt: str, anio: str) -> str | None:
    mes = MESES_TEXTO.get(mes_txt.lower()[:3]) or MESES_TEXTO.get(mes_txt.lower())
    if not mes:
        return None
    return f"{int(dia):02d}/{mes:02d}/{anio}"


def _extraer_fecha_extracto(text: str) -> str | None:
    if m := re.search(r"(\d{2}/\d{2}/\d{4})", text):
        return m.group(1)
    if m := ADDI_FECHA.search(text):
        return _fecha_desde_texto(m.group(1), m.group(2), m.group(3))
    if m := re.search(r"(\d{1,2})\s+de\s+(\w+)\.?\s+de\s+(\d{4})", text, re.I):
        return _fecha_desde_texto(m.group(1), m.group(2), m.group(3))
    return None


def _meta_periodo(text: str) -> tuple[str | None, str | None]:
    m = re.search(r"Desde:\s*(\d{2}/\d{2}/\d{4}).*?Hasta:\s*(\d{2}/\d{2}/\d{4})", text, re.S)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"DESDE:\s*(\d{4}/\d{2}/\d{2})\s+HASTA:\s*(\d{4}/\d{2}/\d{2})", text)
    if m:
        d1 = "/".join(reversed(m.group(1).split("/")))
        d2 = "/".join(reversed(m.group(2).split("/")))
        return d1, d2
    m = re.search(r"período de:\s*(\d{4}/\d{2}/\d{2})\s+a\s+(\d{4}/\d{2}/\d{2})", text, re.I)
    if m:
        d1 = "/".join(reversed(m.group(1).split("/")))
        d2 = "/".join(reversed(m.group(2).split("/")))
        return d1, d2
    return None, None


def _meta_titular(text: str) -> str | None:
    if m := re.search(r"Nombres y Apellidos\s+(.+)", text):
        return m.group(1).strip()
    if m := re.search(r"Extracto de cuenta de ahorro de:\s*\n(.+)", text, re.I):
        return m.group(1).strip()
    return None


def _parse_movimientos_falabella(lines: list[str], start: int) -> tuple[list[dict], int, str | None]:
    transacciones: list[dict] = []
    producto = None
    i = start

    while i < len(lines) and not DATE_FULL.match(lines[i]):
        if lines[i] in ("RESUMEN", "Titular"):
            break
        i += 1

    while i < len(lines):
        if lines[i] in ("RESUMEN", "Titular") or lines[i].startswith("Defensor"):
            if lines[i] == "RESUMEN":
                for j in range(i, min(i + 30, len(lines))):
                    if lines[j] in ("CUENTA DE AHORROS", "CUENTA PAC"):
                        producto = lines[j]
                        break
            break
        if not DATE_FULL.match(lines[i]):
            i += 1
            continue

        fecha = lines[i]
        i += 1
        desc_parts: list[str] = []
        while i < len(lines) and not AMOUNT_CO.match(lines[i]):
            if lines[i] and lines[i] != ".":
                desc_parts.append(lines[i])
            i += 1
        if i + 2 >= len(lines):
            break
        credito = parse_col_amount(lines[i])
        debito = parse_col_amount(lines[i + 1])
        i += 3
        desc = " ".join(desc_parts).strip()
        if credito > 0:
            transacciones.append(
                {"fecha": fecha, "descripcion": desc, "monto": credito, "tipo": "INGRESO"}
            )
        if debito > 0:
            transacciones.append(
                {"fecha": fecha, "descripcion": desc, "monto": debito, "tipo": "EGRESO"}
            )

    return transacciones, i, producto


def _bloques_cuenta_falabella(lines: list[str]) -> list[tuple[int, str | None]]:
    """Índices donde empieza cada cuenta (Titular + número de cuenta)."""
    bloques: list[tuple[int, str | None]] = []
    i = 0
    while i < len(lines):
        if lines[i] == "Titular" and i + 1 < len(lines) and lines[i + 1] == "Número Cuenta":
            cuenta = None
            for j in range(i + 2, min(i + 8, len(lines))):
                if lines[j].isdigit() and len(lines[j]) >= 10:
                    cuenta = lines[j]
                    break
            bloques.append((i, cuenta))
        i += 1
    return bloques


def parse_falabella(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines()]
    titular = _meta_titular(text)
    bloques = _bloques_cuenta_falabella(lines)

    if not bloques:
        bloques = [(0, None)]

    cuentas: list[dict] = []
    for idx, (inicio, numero_cuenta) in enumerate(bloques):
        fin = bloques[idx + 1][0] if idx + 1 < len(bloques) else len(lines)
        segmento = lines[inicio:fin]
        texto_seg = "\n".join(segmento)
        desde, hasta = _meta_periodo(texto_seg)

        transacciones: list[dict] = []
        producto = None
        i = 0
        while i < len(segmento):
            is_block = segmento[i] == "DETALLE DE MOVIMIENTOS" or (
                segmento[i] == "FECHA"
                and i + 1 < len(segmento)
                and "TIPO TRANSACCI" in segmento[i + 1]
            )
            if not is_block:
                i += 1
                continue
            movs, i, prod = _parse_movimientos_falabella(segmento, i + 1)
            transacciones.extend(movs)
            producto = producto or prod
            i += 1

        if not transacciones and not numero_cuenta:
            continue

        cuenta = {
            "entidad": "Banco Falabella",
            "numero_cuenta": numero_cuenta,
            "producto": producto,
            "transacciones": transacciones,
        }
        if desde:
            cuenta["periodo_desde"] = desde
        if hasta:
            cuenta["periodo_hasta"] = hasta
        cuentas.append(cuenta)

    if len(cuentas) == 1:
        result = {"entidad": "Banco Falabella", "banco": "Banco Falabella", **cuentas[0]}
        if titular:
            result["titular"] = titular
        return result

    return {
        "entidad": "Banco Falabella",
        "banco": "Banco Falabella",
        "titular": titular,
        "cuentas": cuentas,
        "transacciones": [],
    }


def parse_nequi(text: str) -> dict:
    transacciones: list[dict] = []
    numero_cuenta = None
    if m := re.search(r"Número de cuenta de ahorro:\s*(\d+)", text):
        numero_cuenta = m.group(1)

    for line in text.splitlines():
        line = line.strip()
        if m := NEQUI_LINE.match(line):
            fecha, desc, valor = m.groups()
            amount = parse_us_amount(valor)
            transacciones.append(
                {
                    "fecha": fecha,
                    "descripcion": desc.strip(),
                    "monto": abs(amount),
                    "tipo": "INGRESO" if amount > 0 else "EGRESO",
                }
            )

    desde, hasta = _meta_periodo(text)
    result = {"entidad": "Nequi", "banco": "Nequi", "producto": "Cuenta de ahorro", "transacciones": transacciones}
    if numero_cuenta:
        result["numero_cuenta"] = numero_cuenta
    if desde:
        result["periodo_desde"] = desde
    if hasta:
        result["periodo_hasta"] = hasta
    return result


def parse_bancolombia_cuenta(text: str) -> dict:
    transacciones: list[dict] = []
    year = "2025"
    if m := re.search(r"DESDE:\s*(\d{4})/\d{2}/\d{2}", text):
        year = m.group(1)

    numero_cuenta = None
    if m := re.search(r"NÚMERO\s+(\d+)", text):
        numero_cuenta = m.group(1)

    in_mov = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("FECHA DESCRIPCIÓN"):
            in_mov = True
            continue
        if not in_mov:
            continue
        if line.startswith("FIN ESTADO"):
            break
        if m := BCO_CUENTA_LINE.match(line):
            dd_mm, desc, valor, _saldo = m.groups()
            amount = parse_money_token(valor)
            if amount == 0:
                continue
            dia, mes = dd_mm.split("/")
            transacciones.append(
                {
                    "fecha": f"{int(dia):02d}/{int(mes):02d}/{year}",
                    "descripcion": desc.strip(),
                    "monto": abs(amount),
                    "tipo": "INGRESO" if amount > 0 else "EGRESO",
                }
            )

    desde, hasta = _meta_periodo(text)
    result = {
        "entidad": "Bancolombia",
        "banco": "Bancolombia",
        "producto": "Cuenta de ahorros",
        "transacciones": transacciones,
    }
    if numero_cuenta:
        result["numero_cuenta"] = numero_cuenta
    if desde:
        result["periodo_desde"] = desde
    if hasta:
        result["periodo_hasta"] = hasta
    return result


def parse_bancolombia_tarjeta(text: str) -> dict:
    transacciones: list[dict] = []
    vistos: set[tuple] = set()

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("DCF:") or line.startswith("Pag."):
            continue
        if m := BCO_TARJETA_LINE.match(line):
            fecha, desc, cargo = m.groups()
            clave = (fecha, desc.strip(), cargo)
            if clave in vistos:
                continue
            vistos.add(clave)
            monto = parse_money_token(cargo)
            if monto == 0:
                continue
            es_abono = "abono" in desc.lower() or cargo.endswith("-") or line.endswith("-")
            transacciones.append(
                {
                    "fecha": fecha,
                    "descripcion": desc.strip(),
                    "monto": abs(monto),
                    "tipo": "INGRESO" if es_abono else "EGRESO",
                }
            )

    numero_tarjeta = None
    if m := re.search(r"\*{4,}(\d{4})", text):
        numero_tarjeta = m.group(1)

    result = {
        "entidad": "Bancolombia",
        "banco": "Bancolombia",
        "producto": "Tarjeta de crédito",
        "transacciones": transacciones,
    }
    if numero_tarjeta:
        result["numero_cuenta"] = numero_tarjeta
    if m := re.search(r"Desde:\s*(\d{2}/\d{2}/\d{4})\s+Hasta:\s*(\d{2}/\d{2}/\d{4})", text):
        result["periodo_desde"] = m.group(1)
        result["periodo_hasta"] = m.group(2)
    return result


def parse_bancolombia_credito(text: str, nombre: str = "") -> dict:
    transacciones: list[dict] = []
    fecha = None
    if m := re.search(r"FECHA CORTE EXTRACTO\s+(\d{1,2}/\d{1,2}/\d{4})", text):
        fecha = m.group(1)
    elif m := re.search(r"FECHA DE PAGO:\s*(\d{1,2}/\d{1,2}/\d{4})", text):
        fecha = m.group(1)

    obligacion = None
    if m := re.search(r"OBLIGACI[OÓ]N N[º°]:\s*(\S+)", text):
        obligacion = m.group(1).strip()

    for line in text.splitlines():
        line = line.strip()
        if m := BCO_CREDITO_LINE.match(line):
            concepto, val1, val2 = m.groups()
            if concepto.upper() == "TOTAL":
                continue
            cuota = val2 if val2 else val1
            monto = parse_money_token(cuota.replace(" ", ""))
            if monto == 0:
                continue
            transacciones.append(
                {
                    "fecha": fecha or "N/A",
                    "descripcion": f"Cuota crédito — {concepto}",
                    "monto": monto,
                    "tipo": "EGRESO",
                }
            )

    result = {
        "entidad": "Bancolombia",
        "banco": "Bancolombia",
        "producto": "Crédito",
        "transacciones": transacciones,
    }
    if obligacion:
        result["numero_cuenta"] = obligacion
    return result


def parse_bancolombia_consolidado(text: str) -> dict:
    transacciones: list[dict] = []
    periodo = None
    if m := re.search(r"Per[ií]odo:\s*(\d{4}/\d{2}/\d{2})\s*hasta\s*(\d{4}/\d{2}/\d{2})", text, re.I):
        d1 = "/".join(reversed(m.group(1).split("/")))
        d2 = "/".join(reversed(m.group(2).split("/")))
        periodo = (d1, d2)

    for line in text.splitlines():
        line = line.strip()
        if m := BCO_CONSOLIDADO_LINE.match(line):
            concepto, _ops, valor = m.groups()
            monto = parse_money_token(valor.replace(" ", ""))
            if monto == 0:
                continue
            transacciones.append(
                {
                    "fecha": periodo[1] if periodo else "N/A",
                    "descripcion": concepto.strip(),
                    "monto": monto,
                    "tipo": "EGRESO",
                }
            )

    result = {
        "entidad": "Bancolombia",
        "banco": "Bancolombia",
        "producto": "Reporte costos / consolidado",
        "transacciones": transacciones,
    }
    if periodo:
        result["periodo_desde"] = periodo[0]
        result["periodo_hasta"] = periodo[1]
    return result


def parse_banco_bogota(text: str) -> dict:
    transacciones: list[dict] = []
    numero_cuenta = None
    if m := re.search(r"Cuenta Número:\s*(\d+)", text):
        numero_cuenta = m.group(1)

    year = "2025"
    if m := re.search(r"FECHA EXTRACTO\s+\w+\s+-\s+\w+\s+(\d{4})", text):
        year = m.group(1)
    elif m := re.search(r"/(\d{4})", text):
        year = m.group(1)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    in_mov = False
    current: dict | None = None

    def flush(desc: str, valor: str, dd_mm: str, year_hint: str | None = None) -> None:
        monto = parse_us_amount(valor)
        if monto == 0:
            return
        fecha_full = None
        if m := re.search(r"(\d{2}/\d{2}/\d{4})", desc):
            fecha_full = m.group(1)
        elif dd_mm:
            yr = year_hint or year
            d, mo = dd_mm.split("/")
            fecha_full = f"{d}/{mo}/{yr}"
        transacciones.append(
            {
                "fecha": fecha_full or "N/A",
                "descripcion": desc.strip(),
                "monto": abs(monto),
                "tipo": "INGRESO" if monto > 0 else "EGRESO",
            }
        )

    for line in lines:
        if "Descripción del Movimiento" in line:
            in_mov = True
            continue
        if not in_mov or "FIN MOVIMIENTOS" in line:
            if "FIN MOVIMIENTOS" in line:
                break
            continue

        m_start = BOGOTA_MOV_START.match(line)
        if m_start:
            if current:
                joined = " ".join(current["parts"])
                if am := BOGOTA_AMOUNTS.search(joined):
                    flush(current["parts"][0], am.group(1), current["dd_mm"])
            dd_mm, cod, rest = m_start.groups()
            parts = [f"{cod} {rest}".strip()] if rest else [cod]
            if am := BOGOTA_AMOUNTS.search(line):
                flush(" ".join(parts), am.group(1), dd_mm)
                current = None
            else:
                current = {"dd_mm": dd_mm, "parts": parts}
            continue

        if current:
            if am := BOGOTA_AMOUNTS.search(line):
                current["parts"].append(line[: am.start()].strip())
                flush(" ".join(p for p in current["parts"] if p), am.group(1), current["dd_mm"])
                current = None
            else:
                current["parts"].append(line)

    if current:
        joined = " ".join(current["parts"])
        if am := BOGOTA_AMOUNTS.search(joined):
            flush(joined, am.group(1), current["dd_mm"])

    result = {
        "entidad": "Banco de Bogotá",
        "banco": "Banco de Bogotá",
        "producto": "Cuenta de ahorros",
        "transacciones": transacciones,
    }
    if numero_cuenta:
        result["numero_cuenta"] = numero_cuenta
    return result


def parse_rappi(text: str) -> dict:
    transacciones: list[dict] = []
    numero_cuenta = None
    if m := re.search(r"Número de cuenta:\s*(\d+)", text):
        numero_cuenta = m.group(1)

    fecha = "N/A"
    if m := re.search(r"Periodo\s*\n\s*\d+\s+(\w+)\s+-\s+\d+\s+(\w+)\s+\(\d+", text, re.I):
        mes = MESES_TEXTO.get(m.group(2).lower()[:3])
        if mes and (ym := re.search(r"generado el\s*\n\s*\d+ de (\w+) de (\d{4})", text, re.I)):
            fecha = f"28/{mes:02d}/{ym.group(2)}"

    resumen = {
        "Abonos": "INGRESO",
        "Intereses ganados": "INGRESO",
        "Retiros": "EGRESO",
        "Comisiones": "EGRESO",
        "GMF 4x1000": "EGRESO",
        "Retención en la fuente": "EGRESO",
        "Iva": "EGRESO",
    }
    lines = text.splitlines()
    for i, line in enumerate(lines):
        etiqueta = line.strip()
        if etiqueta in resumen and i + 1 < len(lines):
            val = lines[i + 1].strip().replace("$", "")
            if val and val != "$":
                try:
                    monto = parse_us_amount(val) if "." in val and "," not in val else parse_col_amount(val)
                except ValueError:
                    continue
                if monto > 0:
                    transacciones.append(
                        {
                            "fecha": fecha,
                            "descripcion": f"Resumen — {etiqueta}",
                            "monto": monto,
                            "tipo": resumen[etiqueta],
                        }
                    )

    for line in lines:
        line = line.strip()
        if m := re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$?([\d.,]+)$", line):
            fecha_m, desc, val = m.groups()
            monto = parse_col_amount(val) if "," in val else parse_us_amount(val)
            if monto > 0:
                transacciones.append(
                    {
                        "fecha": fecha_m,
                        "descripcion": desc.strip(),
                        "monto": monto,
                        "tipo": "INGRESO",
                    }
                )

    result = {"entidad": "RappiPay", "banco": "RappiPay", "producto": "RappiCuenta", "transacciones": transacciones}
    if numero_cuenta:
        result["numero_cuenta"] = numero_cuenta
    return result


def parse_nu(text: str, nombre: str = "") -> dict:
    transacciones: list[dict] = []
    numero_cuenta = None
    if m := re.search(r"Número de Cuenta\s*(\d+)", text):
        numero_cuenta = m.group(1)

    year = None
    fecha_corte = None
    if m := NU_PERIOD_LINE.search(text):
        _dia_ini, dia_fin, mes_txt, year = m.groups()
        mes = NU_MESES.get(mes_txt.lower()[:3])
        if mes and year:
            year = int(year)
            fecha_corte = f"{int(dia_fin):02d}/{mes:02d}/{year}"

    last_fecha = fecha_corte
    in_mov = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "Movimientos":
            in_mov = True
            continue
        if not in_mov:
            continue
        if line.startswith("No hiciste movimientos"):
            continue
        if (
            line.startswith("Los rendimientos se pagan")
            or line.startswith("Nu Financiera")
            or line.startswith("Nu Colombia")
            or line.startswith("Nu.")
            or line.startswith("Nu Compañía")
            or line.startswith("¿Tienes preguntas")
            or re.match(r"^\d+\s*/\s*\d+$", line)
        ):
            in_mov = False
            continue

        if m := NU_GMF_LINE.match(line):
            monto = parse_col_amount(m.group(2))
            if monto == 0:
                continue
            transacciones.append(
                {
                    "fecha": last_fecha or "N/A",
                    "descripcion": "Impuesto del 4x1000",
                    "monto": monto,
                    "tipo": "INGRESO" if m.group(1) == "+" else "EGRESO",
                }
            )
            continue

        if m := NU_MOV_LINE.match(line):
            dia, mes_abr, desc, signo, monto_txt = m.groups()
            mes = NU_MESES.get(mes_abr.lower()[:3])
            if mes and year:
                last_fecha = f"{int(dia):02d}/{mes:02d}/{year}"
            monto = parse_col_amount(monto_txt)
            if monto == 0:
                continue
            transacciones.append(
                {
                    "fecha": last_fecha or "N/A",
                    "descripcion": desc.strip(),
                    "monto": monto,
                    "tipo": "INGRESO" if signo == "+" else "EGRESO",
                }
            )
            continue

        if m := NU_REND_LINE.match(line):
            monto = parse_col_amount(m.group(1))
            if monto > 0:
                transacciones.append(
                    {
                        "fecha": fecha_corte or last_fecha or "N/A",
                        "descripcion": "Rendimiento total de cuenta",
                        "monto": monto,
                        "tipo": "INGRESO",
                    }
                )

    desde, hasta = None, fecha_corte
    if m := NU_PERIOD_LINE.search(text):
        dia_ini, dia_fin, mes_txt, yr = m.groups()
        mes = NU_MESES.get(mes_txt.lower()[:3])
        if mes:
            desde = f"{int(dia_ini):02d}/{mes:02d}/{yr}"
            hasta = f"{int(dia_fin):02d}/{mes:02d}/{yr}"

    result = {"entidad": "Nu", "banco": "Nu", "producto": "Cuenta Nu", "transacciones": transacciones}
    if numero_cuenta:
        result["numero_cuenta"] = numero_cuenta
    if desde:
        result["periodo_desde"] = desde
    if hasta:
        result["periodo_hasta"] = hasta
    return result


def parse_proteccion(text: str) -> dict:
    transacciones: list[dict] = []
    fecha = _extraer_fecha_extracto(text) or "N/A"
    patrones = [
        (r"Aportes obligatorios abonados a mi cuenta de ahorro individual en el trimestre\s*\$\s*([\d.,]+)", "Aportes obligatorios trimestre", "INGRESO"),
        (r"Mis rendimientos del trimestre\s*\$\s*([\d.,]+)", "Rendimientos trimestre", "INGRESO"),
        (r"Mis aportes voluntarios netos del trimestre\s*\$\s*([\d.,]+)", "Aportes voluntarios netos", "INGRESO"),
        (r"Aportes Obligatorios\s+Aportes Voluntarios\s+\$\s*([\d.,]+)", "Aportes obligatorios acumulados", "INGRESO"),
    ]
    for pat, desc, tipo in patrones:
        if m := re.search(pat, text, re.I):
            monto = parse_col_amount(m.group(1))
            if monto > 0:
                transacciones.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo": tipo})

    return {
        "entidad": "Protección",
        "banco": "Protección",
        "producto": "Pensiones obligatorias",
        "titular": _meta_titular(text),
        "transacciones": transacciones,
    }


def parse_cooperativa_recibo(text: str) -> dict:
    transacciones: list[dict] = []
    fecha = _extraer_fecha_extracto(text) or "N/A"
    if m := re.search(r"(\d{2}/\d{2}/\d{4})\s+\$?([\d.,]+)\s+\d{10}", text):
        fecha = m.group(1)

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("("):
            continue
        if re.match(r"^[A-ZÁÉÍÓÚÑ\s]{10,}$", line) and "$" not in line:
            continue
        if m := COOP_CONCEPTO_COD.match(line):
            _cod, desc, monto_txt = m.groups()
            monto = parse_col_amount(monto_txt)
            if monto > 0:
                transacciones.append(
                    {"fecha": fecha, "descripcion": desc.strip(), "monto": monto, "tipo": "EGRESO"}
                )
            continue
        if m := COOP_CONCEPTO.match(line):
            desc, monto_txt = m.groups()
            if desc.upper().startswith("APORTE") or "CUOTA" in desc.upper() or "RECORDAR" in desc.upper() or "EXEQUIAL" in desc.upper():
                monto = parse_col_amount(monto_txt)
                if monto > 0:
                    transacciones.append(
                        {"fecha": fecha, "descripcion": desc.strip(), "monto": monto, "tipo": "EGRESO"}
                    )

    if not transacciones and (m := re.search(r"(\d{2}/\d{2}/\d{4})\s+\$?([\d.,]+)", text)):
        transacciones.append(
            {
                "fecha": m.group(1),
                "descripcion": "Pago recibo cooperativa",
                "monto": parse_col_amount(m.group(2)),
                "tipo": "EGRESO",
            }
        )

    return {
        "entidad": "Cooperativa",
        "banco": "Cooperativa",
        "producto": "Crédito / aportes",
        "transacciones": transacciones,
    }


def parse_addi(text: str) -> dict:
    transacciones: list[dict] = []
    fecha = _extraer_fecha_extracto(text) or "N/A"

    if m := ADDI_PAGO_MIN.search(text):
        try:
            monto = parse_col_amount(m.group(1).replace(" ", "").split("\n")[0])
            if monto > 0:
                transacciones.append(
                    {"fecha": fecha, "descripcion": "Pago mínimo Addi", "monto": monto, "tipo": "EGRESO"}
                )
        except ValueError:
            pass

    for line in text.splitlines():
        line = line.strip().replace("\u00a0", " ")
        if m := re.match(
            r"^([a-f0-9]{6})\s+\$?\s*([\d.,]+)\s+\$?\s*([\d.,]+)\s+\$?\s*([\d.,]+)",
            line,
            re.I,
        ):
            credito, capital, interes, fianza = m.groups()
            for etiqueta, val in [
                ("Pago a capital", capital),
                ("Intereses corrientes", interes),
                ("Fianza / respaldo", fianza),
            ]:
                try:
                    monto = parse_col_amount(val)
                except ValueError:
                    continue
                if monto > 0 and not any(credito in t["descripcion"] and etiqueta in t["descripcion"] for t in transacciones):
                    transacciones.append(
                        {
                            "fecha": fecha,
                            "descripcion": f"Addi {credito} — {etiqueta}",
                            "monto": monto,
                            "tipo": "EGRESO",
                        }
                    )

    return {"entidad": "Addi", "banco": "Addi", "producto": "Crédito", "transacciones": transacciones}


def parse_nu_prestamo(text: str) -> dict:
    transacciones: list[dict] = []
    fecha = _extraer_fecha_extracto(text) or "N/A"
    credito = None
    if m := re.search(r"No\.\s*Cr[eé]dito:\s*(\S+)", text):
        credito = m.group(1)

    monto = None
    if m := re.search(r"(\d{2}/\d{2}/\d{4})\s+\d+/\d+\s+([\d,]+)", text):
        fecha = m.group(1)
        monto = parse_us_amount(m.group(2))
    elif m := re.search(r"\$([\d,]+)", text):
        monto = parse_us_amount(m.group(1))

    if monto and monto > 0:
        transacciones.append(
            {
                "fecha": fecha,
                "descripcion": f"Cuota préstamo Nu {credito or ''}".strip(),
                "monto": monto,
                "tipo": "EGRESO",
            }
        )

    return {
        "entidad": "Nu",
        "banco": "Nu",
        "producto": "Préstamo Nu",
        "transacciones": transacciones,
        "numero_cuenta": credito,
    }


def parse_ahorro_generico(text: str) -> dict:
    transacciones: list[dict] = []
    numero_cuenta = None
    if m := re.search(r"(\d{15,})", text):
        numero_cuenta = m.group(1)

    fecha = _extraer_fecha_extracto(text) or "N/A"
    if m := re.search(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$?([\d.,]+)\s+\$?([\d.,]+)\s*$", text, re.M):
        fecha, desc, _saldo_ant, valor = m.groups()
        monto = parse_col_amount(valor)
        if monto > 0:
            transacciones.append(
                {"fecha": fecha, "descripcion": desc.strip(), "monto": monto, "tipo": "INGRESO"}
            )

    return {
        "entidad": "Cooperativa",
        "banco": "Cooperativa",
        "producto": "Cuenta de ahorros",
        "transacciones": transacciones,
        "numero_cuenta": numero_cuenta,
    }


def parse_recibo_credito(text: str) -> dict:
    return parse_cooperativa_recibo(text)


def parse_bancolombia_resumen_cuentas(text: str) -> dict:
    """Extracto consolidado mensual sin detalle de movimientos."""
    transacciones: list[dict] = []
    fecha_corte = None
    if m := re.search(r"Fecha de Corte\s+(\d{4}/\d{2}/\d{2})", text):
        parts = m.group(1).split("/")
        fecha_corte = f"{parts[2]}/{parts[1]}/{parts[0]}"

    bloques = re.split(r"(?=CUENTA DE AHORROS)", text)
    for bloque in bloques:
        if "Cuenta No." not in bloque:
            continue
        numero = None
        if m := re.search(r"Cuenta No\.\s*(\d+)", bloque):
            numero = m.group(1)
        abonos = cargos = None
        if m := re.search(r"Total Abonos\s*\$\s*([\d.,]+)", bloque):
            abonos = parse_money_token(m.group(1))
        if m := re.search(r"Total Cargos\s*\$\s*([\d.,]+)", bloque):
            cargos = parse_money_token(m.group(1))
        if abonos and abonos > 0:
            transacciones.append(
                {
                    "fecha": fecha_corte or "N/A",
                    "descripcion": f"Total abonos cuenta {numero or '?'}",
                    "monto": abonos,
                    "tipo": "INGRESO",
                    "numero_cuenta": numero,
                }
            )
        if cargos and cargos > 0:
            transacciones.append(
                {
                    "fecha": fecha_corte or "N/A",
                    "descripcion": f"Total cargos cuenta {numero or '?'}",
                    "monto": cargos,
                    "tipo": "EGRESO",
                    "numero_cuenta": numero,
                }
            )

    return {
        "entidad": "Bancolombia",
        "banco": "Bancolombia",
        "producto": "Resumen consolidado cuentas",
        "transacciones": transacciones,
    }


def detectar_y_parsear(text: str, nombre: str) -> dict:
    nombre_l = nombre.lower()
    texto_l = text.lower()

    if "DETALLE DE MOVIMIENTOS" in text:
        return parse_falabella(text)
    if "Fecha del movimiento Descripción Valor Saldo" in text:
        return parse_nequi(text)

    if "bancodebogota.com" in texto_l or (
        "extracto cuenta ahorros" in texto_l and "cuenta número:" in texto_l and "bogota" in texto_l
    ):
        return parse_banco_bogota(text)

    if "cuentanu" in nombre_l or "nu placa" in texto_l or "llegó tu extracto" in texto_l:
        return parse_nu(text, nombre)

    if "no. crédito:" in texto_l or "no. credito:" in texto_l:
        if "nu" in texto_l or "préstamo nu" in texto_l or "prestamo nu" in texto_l:
            return parse_nu_prestamo(text)
        return parse_bancolombia_credito(text, nombre)

    if "generado :" in texto_l and re.search(r"\d{5}-\d{2}", text):
        return parse_nu_prestamo(text)

    if "aporte social" in texto_l:
        return parse_cooperativa_recibo(text)

    if (
        "addi.com" in texto_l
        or "adelante soluciones financieras" in texto_l
        or re.search(r"extracto-\d{4}-\d{2}-\d{2}", nombre_l)
        or ("algunos créditos de addi" in texto_l)
    ):
        return parse_addi(text)

    if (
        "estado de cuenta en:" in texto_l
        or "tarjeta_mastercard" in nombre_l
        or ("tarjeta" in nombre_l and "mastercard" in nombre_l)
        or "mastercard_detallado" in nombre_l
        or re.search(r"(?:^|_)(5615)(?:_|\.|$)", nombre_l)
    ):
        return parse_bancolombia_tarjeta(text)

    if "reporte anual" in texto_l or "comisiones_consolidadas" in nombre_l:
        return parse_bancolombia_consolidado(text)

    if re.search(r"^\d{10}_", nombre_l) and "obligación" in texto_l:
        return parse_bancolombia_credito(text, nombre)

    if "obligación" in texto_l or "obligacion" in texto_l or "credito" in nombre_l:
        return parse_bancolombia_credito(text, nombre)

    if (
        "cuenta de ahorros" in texto_l
        and "total abonos" in texto_l
        and "fecha descripción" not in texto_l
    ) or ("consolidado" in nombre_l and "cuenta de ahorros" in texto_l):
        return parse_bancolombia_resumen_cuentas(text)

    if (
        "fecha descripción" in texto_l
        or ("cuenta de ahorros" in texto_l and "número" in texto_l)
        or "cta_ahorros" in nombre_l
        or re.search(r"^\d{11}_", nombre_l)
        or re.search(r"^\d{11}\.", nombre_l)
        or ("extracto_" in nombre_l and "estado de cuenta" in texto_l)
    ):
        parsed = parse_bancolombia_cuenta(text)
        if parsed["transacciones"] or "bancolombia" not in texto_l:
            return parsed
        resumen = parse_bancolombia_resumen_cuentas(text)
        if resumen["transacciones"]:
            return resumen
        return parsed

    if "bancolombia.com" in texto_l and "estado de cuenta" in texto_l:
        return parse_bancolombia_cuenta(text)

    if "RappiCuenta" in text or "RappiPay" in text:
        return parse_rappi(text)
    if "pensionesobligatorias" in nombre_l or "proteccion.com" in texto_l:
        return parse_proteccion(text)

    if re.search(r"\d{2}/\d{2}/\d{4}\s+A\s+\d{2}/\d{2}/\d{4}", text) and "abono interes" in texto_l:
        return parse_ahorro_generico(text)

    return {"entidad": "Desconocido", "banco": "Desconocido", "transacciones": [], "archivo": nombre}


def procesar_archivo_texto(ruta: Path) -> dict:
    datos = detectar_y_parsear(ruta.read_text(encoding="utf-8"), ruta.name)
    return enriquecer(datos, ruta)
