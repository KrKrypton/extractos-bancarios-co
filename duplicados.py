"""Detección y eliminación de documentos duplicados en el pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config import (
    EXTRACTOS_DIR,
    SALIDA_CONSOLIDADO_DIR,
    SALIDA_JSON_DIR,
    SALIDA_MD_DIR,
    SALIDA_PDF_DIR,
    SALIDA_TEXTO_DIR,
)
from markdown_export import ruta_md_desde_texto
from procesador_ollama import ruta_json_salida

TAMANO_MINIMO_PDF = 1024


def hash_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def periodo_extracto(nombre: str) -> tuple[int, int] | None:
    if m := re.search(r"extracto_cuenta(\d{6})", nombre, re.I):
        periodo = m.group(1)
        return int(periodo[:4]), int(periodo[4:6])
    if m := re.search(r"Extracto_(\d{4})(\d{2})_", nombre, re.I):
        return int(m.group(1)), int(m.group(2))
    if m := re.search(r"_(\d{4})(\d{2})_", nombre):
        anio, mes = int(m.group(1)), int(m.group(2))
        if 1 <= mes <= 12:
            return anio, mes
    if m := re.search(r"(\d{4})-(\d{2})", nombre):
        return int(m.group(1)), int(m.group(2))
    return None


def periodo_carpeta(ruta: Path) -> tuple[int, int] | None:
    if m := re.match(r"(\d{4})-(\d{2})", ruta.parent.name):
        return int(m.group(1)), int(m.group(2))
    return None


def puntuacion_canonica(ruta: Path) -> tuple:
    """Menor puntuación = archivo más apropiado para conservar."""
    periodo = periodo_extracto(ruta.name)
    carpeta = periodo_carpeta(ruta)
    distancia = 9999
    if periodo and carpeta:
        distancia = abs(
            (periodo[0] * 12 + periodo[1]) - (carpeta[0] * 12 + carpeta[1])
        )
    return (distancia, len(str(ruta)), str(ruta))


def rutas_asociadas_desde_txt(txt: Path) -> list[Path]:
    txt = txt.resolve()
    try:
        relativa = txt.relative_to(SALIDA_TEXTO_DIR.resolve())
    except ValueError:
        relativa = Path(txt.name)

    candidatos = [
        txt,
        ruta_json_salida(txt),
        ruta_md_desde_texto(txt),
        SALIDA_PDF_DIR / relativa.with_suffix(".pdf"),
        EXTRACTOS_DIR / relativa.with_suffix(".pdf"),
    ]
    return [p for p in candidatos if p.exists()]


def rutas_asociadas_desde_pdf(pdf: Path) -> list[Path]:
    pdf = pdf.resolve()
    try:
        relativa = pdf.relative_to(EXTRACTOS_DIR.resolve())
    except ValueError:
        relativa = Path(pdf.name)

    txt = SALIDA_TEXTO_DIR / relativa.with_suffix(".txt")
    candidatos = [
        pdf,
        txt,
        SALIDA_JSON_DIR / relativa.with_suffix(".json"),
        SALIDA_MD_DIR / relativa.with_suffix(".md"),
        SALIDA_PDF_DIR / relativa.with_suffix(".pdf"),
    ]
    return [p for p in candidatos if p.exists()]


@dataclass
class GrupoDuplicado:
    tipo: str
    hash_valor: str
    canonico: str
    duplicados: list[str] = field(default_factory=list)
    archivos_a_borrar: list[str] = field(default_factory=list)


@dataclass
class InformeDuplicados:
    grupos_texto: list[GrupoDuplicado] = field(default_factory=list)
    grupos_pdf: list[GrupoDuplicado] = field(default_factory=list)
    archivos_vacios: list[str] = field(default_factory=list)
    total_archivos_a_borrar: int = 0

    def todos_los_archivos_a_borrar(self) -> list[Path]:
        rutas: list[Path] = []
        for grupo in self.grupos_texto + self.grupos_pdf:
            rutas.extend(Path(p) for p in grupo.archivos_a_borrar)
        rutas.extend(Path(p) for p in self.archivos_vacios)
        return sorted(set(rutas), key=str)


def _agrupar_por_hash(archivos: list[Path]) -> dict[str, list[Path]]:
    grupos: dict[str, list[Path]] = {}
    for archivo in archivos:
        grupos.setdefault(hash_archivo(archivo), []).append(archivo)
    return grupos


def _elegir_canonico(archivos: list[Path]) -> Path:
    return min(archivos, key=puntuacion_canonica)


def analizar_duplicados() -> InformeDuplicados:
    informe = InformeDuplicados()

    textos = sorted(SALIDA_TEXTO_DIR.rglob("*.txt"))
    for hash_valor, archivos in _agrupar_por_hash(textos).items():
        if len(archivos) < 2:
            continue
        canonico = _elegir_canonico(archivos)
        duplicados = [a for a in archivos if a != canonico]
        a_borrar: list[Path] = []
        for dup in duplicados:
            a_borrar.extend(rutas_asociadas_desde_txt(dup))
        a_borrar = sorted(set(a_borrar), key=str)
        informe.grupos_texto.append(
            GrupoDuplicado(
                tipo="texto",
                hash_valor=hash_valor[:12],
                canonico=str(canonico),
                duplicados=[str(d) for d in duplicados],
                archivos_a_borrar=[str(p) for p in a_borrar],
            )
        )

    pdfs = sorted(EXTRACTOS_DIR.rglob("*.pdf"))
    for hash_valor, archivos in _agrupar_por_hash(pdfs).items():
        archivos_utiles = [a for a in archivos if a.stat().st_size >= TAMANO_MINIMO_PDF]
        if len(archivos_utiles) < 2:
            continue
        canonico = _elegir_canonico(archivos_utiles)
        duplicados = [a for a in archivos_utiles if a != canonico]
        a_borrar: list[Path] = []
        for dup in duplicados:
            a_borrar.extend(rutas_asociadas_desde_pdf(dup))
        a_borrar = sorted(set(a_borrar), key=str)
        informe.grupos_pdf.append(
            GrupoDuplicado(
                tipo="pdf",
                hash_valor=hash_valor[:12],
                canonico=str(canonico),
                duplicados=[str(d) for d in duplicados],
                archivos_a_borrar=[str(p) for p in a_borrar],
            )
        )

    vacios: list[Path] = []
    for pdf in pdfs:
        if pdf.stat().st_size < TAMANO_MINIMO_PDF:
            vacios.extend(rutas_asociadas_desde_pdf(pdf))
    informe.archivos_vacios = [str(p) for p in sorted(set(vacios), key=str)]

    informe.total_archivos_a_borrar = len(informe.todos_los_archivos_a_borrar())
    return informe


def imprimir_informe(informe: InformeDuplicados) -> None:
    print(f"Grupos duplicados por texto: {len(informe.grupos_texto)}")
    for grupo in informe.grupos_texto:
        print(f"\n  [{grupo.hash_valor}] conservar: {Path(grupo.canonico).name}")
        for dup in grupo.duplicados:
            print(f"    duplicado: {Path(dup).name} ({Path(dup).parent.name})")

    print(f"\nGrupos duplicados por PDF (hash idéntico): {len(informe.grupos_pdf)}")
    for grupo in informe.grupos_pdf:
        print(f"\n  [{grupo.hash_valor}] conservar: {grupo.canonico}")
        for dup in grupo.duplicados:
            print(f"    duplicado: {dup}")

    if informe.archivos_vacios:
        print(f"\nArchivos vacíos o casi vacíos (< {TAMANO_MINIMO_PDF} B):")
        for ruta in informe.archivos_vacios:
            print(f"  {ruta}")

    print(f"\nTotal de archivos a borrar: {informe.total_archivos_a_borrar}")


def guardar_informe(informe: InformeDuplicados, destino: Path | None = None) -> Path:
    destino = destino or SALIDA_CONSOLIDADO_DIR / "duplicados_reporte.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "grupos_texto": [asdict(g) for g in informe.grupos_texto],
        "grupos_pdf": [asdict(g) for g in informe.grupos_pdf],
        "archivos_vacios": informe.archivos_vacios,
        "total_archivos_a_borrar": informe.total_archivos_a_borrar,
    }
    destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino


def eliminar_duplicados(ejecutar: bool = False) -> InformeDuplicados:
    informe = analizar_duplicados()
    rutas = informe.todos_los_archivos_a_borrar()

    if not rutas:
        print("No se encontraron duplicados para eliminar.")
        return informe

    if not ejecutar:
        print("Modo simulación (--ejecutar para borrar realmente):\n")
        imprimir_informe(informe)
        return informe

    borrados = 0
    for ruta in rutas:
        ruta.unlink()
        borrados += 1
        print(f"  borrado: {ruta}")

    _limpiar_carpetas_vacias()
    print(f"\nEliminados {borrados} archivos.")
    imprimir_informe(informe)
    return informe


def _limpiar_carpetas_vacias() -> None:
    for base in (EXTRACTOS_DIR, SALIDA_TEXTO_DIR, SALIDA_JSON_DIR, SALIDA_MD_DIR, SALIDA_PDF_DIR):
        for carpeta in sorted(base.rglob("*"), reverse=True):
            if carpeta.is_dir() and not any(carpeta.iterdir()):
                carpeta.rmdir()
