import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import requests

from config import SALIDA_JSON_DIR, SALIDA_MD_DIR, SALIDA_TEXTO_DIR
from markdown_export import generar_tabla_markdown, ruta_md_desde_texto


def enviar_a_ollama_local(texto_banco: str, modelo: str = "gemma:4b") -> dict | None:
    """Envía el texto extraído a la IA local en Ollama para estructurarlo en JSON."""
    url_local = "http://localhost:11434/api/generate"

    prompt = f"""
Eres un sistema automatizado de extracción de datos contables.
Tu única función es recibir texto de extractos bancarios y devolver un objeto JSON válido.
REGLA ESTRICTA: NO incluyas saludos, NO des explicaciones, devuelve ÚNICAMENTE el código JSON.
--- EJEMPLO DE SALIDA ESPERADA ---
{{
  "banco": "Nombre del Banco Identificado",
  "transacciones": [
    {{
      "fecha": "DD/MM/YYYY",
      "descripcion": "Descripción exacta del movimiento",
      "monto": 150000.00,
      "tipo": "INGRESO o EGRESO"
    }}
  ]
}}
--- ENTRADA REAL A PROCESAR ---
{texto_banco}
"""
    payload = {
        "model": modelo,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0},
    }

    respuesta_json = None
    try:
        response = requests.post(url_local, json=payload, timeout=300)
        response.raise_for_status()
        respuesta_json = response.json()
        return json.loads(respuesta_json["response"])

    except requests.exceptions.RequestException as e:
        print(f"[SKIP] Ollama no respondió: {e}")
    except json.JSONDecodeError:
        print("[SKIP] Respuesta no es JSON válido.")
        if respuesta_json:
            print("  Respuesta cruda:", respuesta_json.get("response", "")[:200])

    return None


def ruta_json_salida(ruta_texto: Path, destino: Path = SALIDA_JSON_DIR) -> Path:
    ruta_texto = ruta_texto.resolve()
    try:
        relativa = ruta_texto.relative_to(SALIDA_TEXTO_DIR.resolve())
    except ValueError:
        relativa = Path(ruta_texto.name)

    return destino / relativa.with_suffix(".json")


def listar_textos(mes: str | None = None) -> list[Path]:
    if mes:
        carpeta = SALIDA_TEXTO_DIR / mes
        if not carpeta.is_dir():
            raise FileNotFoundError(f"No hay textos extraídos para {mes}: {carpeta}")
        return sorted(carpeta.glob("*.txt"))

    return sorted(SALIDA_TEXTO_DIR.rglob("*.txt"))


@dataclass
class ResultadoOllama:
    ok: list[Path] = field(default_factory=list)
    fallidos: list[str] = field(default_factory=list)


def guardar_resultado(
    archivo_txt: Path,
    datos: dict,
    destino_json: Path = SALIDA_JSON_DIR,
    destino_md: Path = SALIDA_MD_DIR,
) -> Path:
    """Guarda JSON y tabla Markdown espejo del extracto."""
    ruta_json = ruta_json_salida(archivo_txt, destino_json)
    ruta_json.parent.mkdir(parents=True, exist_ok=True)
    ruta_json.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ruta_md = ruta_md_desde_texto(archivo_txt, destino_md)
    generar_tabla_markdown(datos, ruta_md)
    return ruta_json


def procesar_textos(
    archivos: list[Path],
    modelo: str = "gemma:4b",
    destino: Path = SALIDA_JSON_DIR,
) -> ResultadoOllama:
    """Estructura textos con Ollama. Si uno falla, continúa con el siguiente."""
    resultado = ResultadoOllama()

    for archivo in archivos:
        print(f"Ollama ({modelo}): {archivo.name}...")
        texto = archivo.read_text(encoding="utf-8")
        datos = enviar_a_ollama_local(texto, modelo=modelo)
        if not datos:
            resultado.fallidos.append(archivo.name)
            continue

        guardar_resultado(archivo, datos, destino_json=destino)
        resultado.ok.append(ruta_json_salida(archivo, destino))
        print(f"[OK] {archivo.name} → json + md")

    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estructura textos extraídos usando Ollama local."
    )
    parser.add_argument("--modelo", default="gemma:4b")
    parser.add_argument("--mes", help="Solo una carpeta YYYY-MM (por defecto: todas)")
    parser.add_argument("--texto", help="Solo un .txt específico (por defecto: todos)")
    args = parser.parse_args()

    if args.texto:
        archivos = [Path(args.texto)]
    elif args.mes:
        archivos = listar_textos(args.mes)
    else:
        archivos = listar_textos()

    if not archivos:
        print("No hay archivos de texto. Ejecuta primero el desencriptador.")
        return

    print(f"Procesando {len(archivos)} archivo(s)...")
    resultado = procesar_textos(archivos, modelo=args.modelo)
    print(f"\nListo: {len(resultado.ok)}/{len(archivos)} extractos (JSON + Markdown).")
    if resultado.fallidos:
        print(f"Omitidos ({len(resultado.fallidos)}): {', '.join(resultado.fallidos)}")


if __name__ == "__main__":
    main()
