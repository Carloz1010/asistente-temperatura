"""Elige la IA desde .env. Para agregar otra: un archivo nuevo y una línea en _PROVEEDORES."""

import importlib
import os

from dotenv import load_dotenv

from medico_cuarto.proveedores.base import Proveedor

# nombre en .env -> (módulo, clase). El SDK se importa solo si se usa ese proveedor.
_PROVEEDORES: dict[str, tuple[str, str]] = {
    "gemini": ("medico_cuarto.proveedores.gemini", "ProveedorGemini"),
    "claude": ("medico_cuarto.proveedores.claude", "ProveedorClaude"),
}
PROVEEDOR_POR_DEFECTO: str = "gemini"


def crear_proveedor(nombre: str | None = None, modelo: str | None = None) -> Proveedor:
    """Usa los argumentos o, si faltan, PROVEEDOR_IA y MODELO_IA del .env."""
    load_dotenv()
    elegido = (nombre or os.getenv("PROVEEDOR_IA") or PROVEEDOR_POR_DEFECTO).strip().lower()
    if elegido not in _PROVEEDORES:
        raise ValueError(f"Proveedor '{elegido}' desconocido. Opciones: {sorted(_PROVEEDORES)}.")
    ruta_modulo, nombre_clase = _PROVEEDORES[elegido]
    clase = getattr(importlib.import_module(ruta_modulo), nombre_clase)
    return clase(modelo=modelo or os.getenv("MODELO_IA") or None)
