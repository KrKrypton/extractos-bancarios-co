from pathlib import Path

from config import SALIDA_JSON_DIR, SALIDA_MD_DIR, SALIDA_TEXTO_DIR


def ruta_md_desde_json(ruta_json: Path, destino: Path = SALIDA_MD_DIR) -> Path:
    ruta_json = ruta_json.resolve()
    try:
        relativa = ruta_json.relative_to(SALIDA_JSON_DIR.resolve())
    except ValueError:
        relativa = Path(ruta_json.stem + ".md")
    return destino / relativa.with_suffix(".md")


def ruta_md_desde_texto(ruta_texto: Path, destino: Path = SALIDA_MD_DIR) -> Path:
    ruta_texto = ruta_texto.resolve()
    try:
        relativa = ruta_texto.relative_to(SALIDA_TEXTO_DIR.resolve())
    except ValueError:
        relativa = Path(ruta_texto.stem + ".md")
    return destino / relativa.with_suffix(".md")


def generar_tabla_markdown(datos_json: dict, nombre_archivo: str | Path) -> bool:
    """
    Toma el JSON estructurado y crea un archivo Markdown con una tabla estilizada.
    """
    if not datos_json or "transacciones" not in datos_json:
        print("No hay datos válidos para generar el Markdown.")
        return False

    banco = datos_json.get("banco", "Banco Desconocido")
    transacciones = datos_json["transacciones"]

    lineas = [f"# Resumen de Movimientos: {banco}\n"]
    lineas.append("| Fecha | Descripción | Tipo | Monto ($) |")
    lineas.append("| :--- | :--- | :---: | ---: |")

    total_ingresos = 0.0
    total_egresos = 0.0

    for t in transacciones:
        fecha = t.get("fecha", "N/A")
        descripcion = str(t.get("descripcion", "N/A")).replace("|", "\\|")
        tipo = str(t.get("tipo", "N/A")).upper()
        monto = float(t.get("monto", 0))

        if tipo == "INGRESO":
            tipo_visual = "🟢 INGRESO"
            total_ingresos += monto
        else:
            tipo_visual = "🔴 EGRESO"
            total_egresos += monto

        monto_formateado = f"{monto:,.2f}"
        lineas.append(f"| {fecha} | {descripcion} | {tipo_visual} | ${monto_formateado} |")

    balance = total_ingresos - total_egresos
    lineas.append("\n### Resumen Final\n")
    lineas.append(f"- **Total Ingresos:** ${total_ingresos:,.2f}")
    lineas.append(f"- **Total Egresos:** ${total_egresos:,.2f}")
    lineas.append(f"- **Balance Neto:** **${balance:,.2f}**")

    salida = Path(nombre_archivo)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return True
