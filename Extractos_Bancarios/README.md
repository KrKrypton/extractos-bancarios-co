# Carpeta de entrada

Coloca aquí los PDFs de extractos bancarios, organizados por mes:

```
Extractos_Bancarios/
  2024-01/
    extracto_enero.pdf
  2024-02/
    ...
```

Los archivos PDF **no se suben al repositorio** (contienen datos personales). Solo esta guía.

Para procesarlos:

```bash
export CONTADORA_PDF_PASSWORDS="tu_cedula,otra_clave"
./run --solo-texto
```
