#!/usr/bin/env python3
"""Verifica que los parsers funcionen con los ejemplos sintéticos."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from procesador_texto import detectar_y_parsear

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos" / "texto"


class TestEjemplos(unittest.TestCase):
    def _parsear(self, nombre: str) -> dict:
        ruta = EJEMPLOS / nombre
        self.assertTrue(ruta.exists(), f"Falta {nombre}")
        return detectar_y_parsear(ruta.read_text(encoding="utf-8"), ruta.name)

    def test_nequi(self):
        datos = self._parsear("nequi_202401.txt")
        self.assertEqual(datos["entidad"], "Nequi")
        self.assertGreaterEqual(len(datos["transacciones"]), 3)

    def test_bancolombia(self):
        datos = self._parsear("bancolombia_cuenta_202401.txt")
        self.assertEqual(datos["entidad"], "Bancolombia")
        self.assertGreaterEqual(len(datos["transacciones"]), 3)

    def test_nu(self):
        datos = self._parsear("nu_202405.txt")
        self.assertEqual(datos["entidad"], "Nu")
        self.assertGreaterEqual(len(datos["transacciones"]), 3)


if __name__ == "__main__":
    unittest.main()
