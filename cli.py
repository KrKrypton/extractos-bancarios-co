import argparse
import os
from pathlib import Path

from config import EXTRACTOS_DIR, SALIDA_PDF_DIR, SALIDA_TEXTO_DIR


def ruta_salida_espejo(pdf: Path, destino: Path, suffix: str) -> Path:
    pdf = pdf.resolve()
    try:
        relativa = pdf.relative_to(EXTRACTOS_DIR.resolve())
    except ValueError:
        relativa = Path(pdf.name)
    return destino / relativa.with_suffix(suffix)


def ruta_texto_salida(pdf: Path, destino: Path = SALIDA_TEXTO_DIR) -> Path:
    return ruta_salida_espejo(pdf, destino, ".txt")


def ruta_pdf_salida(pdf: Path, destino: Path = SALIDA_PDF_DIR) -> Path:
    return ruta_salida_espejo(pdf, destino, ".pdf")


def listar_pdfs(mes: str | None = None) -> list[Path]:
    if mes:
        carpeta = EXTRACTOS_DIR / mes
        if not carpeta.is_dir():
            raise FileNotFoundError(f"No existe la carpeta de mes: {carpeta}")
        return sorted(carpeta.glob("*.pdf"))

    return sorted(EXTRACTOS_DIR.rglob("*.pdf"))


def normalizar_passwords(valores: list[str]) -> list[str]:
    """Acepta lista con entradas separadas por coma; elimina duplicados."""
    vistos: set[str] = set()
    resultado: list[str] = []

    for valor in valores:
        for clave in valor.split(","):
            clave = clave.strip()
            if clave and clave not in vistos:
                vistos.add(clave)
                resultado.append(clave)

    return resultado


def agregar_filtros_pdf(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--password",
        action="append",
        dest="passwords",
        metavar="CLAVE",
        help=(
            "Contraseña del PDF (cédula, NIT, etc.). "
            "Repetible o separadas por coma. "
            "También: CONTADORA_PDF_PASSWORD o CONTADORA_PDF_PASSWORDS"
        ),
    )
    parser.add_argument("--mes", help="Solo una carpeta YYYY-MM (por defecto: todas)")
    parser.add_argument("--pdf", help="Solo un PDF específico (por defecto: todos)")
    parser.add_argument(
        "--pendientes",
        action="store_true",
        help="Solo PDFs sin .txt en salida/texto (útil para reintentar fallidos)",
    )
    parser.add_argument(
        "--sin-pdf",
        action="store_true",
        help="No guardar copias PDF sin contraseña en salida/pdf/",
    )


def resolver_pdfs(args: argparse.Namespace) -> list[Path]:
    if args.pdf:
        pdfs = [Path(args.pdf)]
    elif args.mes:
        pdfs = listar_pdfs(args.mes)
    else:
        pdfs = listar_pdfs()

    if getattr(args, "pendientes", False):
        pdfs = [p for p in pdfs if not ruta_texto_salida(p).exists()]

    return pdfs


def resolver_passwords(args: argparse.Namespace) -> list[str]:
    raw: list[str] = list(args.passwords or [])

    if not raw:
        for var in ("CONTADORA_PDF_PASSWORD", "CONTADORA_PDF_PASSWORDS"):
            valor = os.environ.get(var, "").strip()
            if valor:
                raw.append(valor)

    passwords = normalizar_passwords(raw)
    if not passwords:
        raise SystemExit(
            "Indica --password (puede repetirse), o define "
            "CONTADORA_PDF_PASSWORD / CONTADORA_PDF_PASSWORDS"
        )
    return passwords
