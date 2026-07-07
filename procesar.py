#!/usr/bin/env python3
"""Pipeline: PDF -> texto -> JSON."""

import argparse

from cli import agregar_filtros_pdf, resolver_passwords, resolver_pdfs
from desencriptador import extraer_pdfs
from procesador_ollama import procesar_textos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Procesa extractos bancarios desde Extractos_Bancarios."
    )
    agregar_filtros_pdf(parser)
    parser.add_argument("--modelo", default="gemma:4b")
    parser.add_argument(
        "--solo-texto",
        action="store_true",
        help="Solo extraer texto, sin Ollama",
    )
    args = parser.parse_args()

    passwords = resolver_passwords(args)
    pdfs = resolver_pdfs(args)

    if not pdfs:
        print("No se encontraron PDFs.")
        return

    print(f"=== Extracción ({len(pdfs)} PDFs, {len(passwords)} claves) ===")
    extraccion = extraer_pdfs(pdfs, passwords, guardar_pdf=not args.sin_pdf)
    print(f"{len(extraccion.ok)}/{len(pdfs)} extraídos.")
    if not args.sin_pdf and extraccion.pdfs:
        print(f"PDFs sin contraseña: {len(extraccion.pdfs)} en salida/pdf/")
    if extraccion.fallidos:
        print(f"Omitidos: {', '.join(extraccion.fallidos)}")

    if args.solo_texto:
        return

    if not extraccion.ok:
        print("Nada que enviar a Ollama.")
        return

    print(f"\n=== Ollama ({args.modelo}) ===")
    ollama = procesar_textos(extraccion.ok, modelo=args.modelo)
    print(f"{len(ollama.ok)}/{len(extraccion.ok)} JSON generados.")
    if ollama.fallidos:
        print(f"Omitidos: {', '.join(ollama.fallidos)}")


if __name__ == "__main__":
    main()
