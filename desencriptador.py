import argparse
from dataclasses import dataclass, field
from pathlib import Path

import pypdf

from cli import agregar_filtros_pdf, resolver_passwords, resolver_pdfs, ruta_pdf_salida, ruta_texto_salida
from config import SALIDA_PDF_DIR, SALIDA_TEXTO_DIR


def _abrir_pdf(ruta_pdf: Path, passwords: list[str]) -> tuple[pypdf.PdfReader, object, str | None]:
    """Abre un PDF; retorna (reader, archivo_abierto, contraseña_usada)."""
    f = open(ruta_pdf, "rb")
    reader = pypdf.PdfReader(f)
    if not reader.is_encrypted:
        return reader, f, None
    for password in passwords:
        if reader.decrypt(password):
            return reader, f, password
    f.close()
    raise ValueError("ninguna contraseña válida")


def _extraer_con_password(ruta_pdf: Path, passwords: list[str]) -> str | None:
    try:
        reader, f, _ = _abrir_pdf(ruta_pdf, passwords)
    except (ValueError, Exception):
        return None

    try:
        partes: list[str] = []
        for page in reader.pages:
            texto_pagina = page.extract_text()
            if texto_pagina:
                partes.append(texto_pagina)
    finally:
        f.close()

    texto = "\n".join(partes)
    return texto if texto.strip() else None


def guardar_pdf_sin_password(
    ruta_pdf: Path,
    passwords: list[str],
    destino: Path = SALIDA_PDF_DIR,
) -> Path | None:
    """Guarda una copia del PDF sin contraseña (los originales no se modifican)."""
    try:
        reader, f, _ = _abrir_pdf(ruta_pdf, passwords)
    except (ValueError, Exception):
        return None

    salida = ruta_pdf_salida(ruta_pdf, destino)
    salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        writer = pypdf.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with open(salida, "wb") as out:
            writer.write(out)
    finally:
        f.close()

    return salida


def extraer_texto_pdf_seguro(ruta_pdf: str | Path, passwords: list[str]) -> str | None:
    """Prueba varias contraseñas; retorna el texto si alguna funciona."""
    ruta_pdf = Path(ruta_pdf)
    if not ruta_pdf.exists():
        print(f"[SKIP] No existe: {ruta_pdf}")
        return None

    try:
        texto = _extraer_con_password(ruta_pdf, passwords)
        if not texto:
            print(f"[SKIP] Ninguna contraseña funcionó: {ruta_pdf.name}")
        return texto

    except Exception as e:
        print(f"[SKIP] Error en {ruta_pdf.name}: {e}")
        return None


@dataclass
class ResultadoExtraccion:
    ok: list[Path] = field(default_factory=list)
    pdfs: list[Path] = field(default_factory=list)
    fallidos: list[str] = field(default_factory=list)


def extraer_pdfs(
    pdfs: list[Path],
    passwords: list[str],
    destino: Path = SALIDA_TEXTO_DIR,
    guardar_pdf: bool = True,
    destino_pdf: Path = SALIDA_PDF_DIR,
) -> ResultadoExtraccion:
    """Extrae texto y, por defecto, guarda copias PDF sin contraseña."""
    resultado = ResultadoExtraccion()

    for pdf in pdfs:
        texto = extraer_texto_pdf_seguro(pdf, passwords)
        if not texto:
            resultado.fallidos.append(pdf.name)
            continue

        salida = ruta_texto_salida(pdf, destino)
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(texto, encoding="utf-8")
        resultado.ok.append(salida)

        if guardar_pdf:
            if copia := guardar_pdf_sin_password(pdf, passwords, destino_pdf):
                resultado.pdfs.append(copia)

        print(f"[OK] {pdf.name}")

    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Desencripta PDFs de Extractos_Bancarios y extrae su texto."
    )
    agregar_filtros_pdf(parser)
    args = parser.parse_args()

    passwords = resolver_passwords(args)
    pdfs = resolver_pdfs(args)

    if not pdfs:
        print("No se encontraron PDFs para procesar.")
        return

    print(f"Procesando {len(pdfs)} PDF(s) con {len(passwords)} contraseña(s)...")
    resultado = extraer_pdfs(pdfs, passwords, guardar_pdf=not args.sin_pdf)
    print(f"\nListo: {len(resultado.ok)}/{len(pdfs)} extraídos.")
    if not args.sin_pdf:
        print(f"PDFs sin contraseña: {len(resultado.pdfs)} → {SALIDA_PDF_DIR}")
    if resultado.fallidos:
        print(f"Omitidos ({len(resultado.fallidos)}): {', '.join(resultado.fallidos)}")


if __name__ == "__main__":
    main()
