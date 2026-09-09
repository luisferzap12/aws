#!/usr/bin/env python3
"""
Agrega preguntas a un banco sin editar el JSON a mano.

Dos modos:

  Interactivo — te va preguntando campo por campo:
      python3 agregar_preguntas.py --banco banco_clf.json

  Importación en lote — lee un archivo de texto con varias preguntas:
      python3 agregar_preguntas.py --banco banco_clf.json --importar nuevas.txt

Formato del archivo de texto (bloques separados por una línea en blanco):

    D: seguridad
    P: ¿Qué servicio guarda secretos y los rota automáticamente?
    I: responsabilidad-compartida.svg
    - AWS Systems Manager Parameter Store
    * AWS Secrets Manager
    - AWS KMS
    - AWS Artifact
    E: Secrets Manager guarda credenciales y las rota sin intervención.
    R: AWS Secrets Manager

  D  dominio (su id o su nombre)      I  imagen, opcional
  P  enunciado                        E  explicación
  -  opción incorrecta                R  referencia, opcional
  *  opción correcta (una o varias)

Las líneas sin prefijo continúan el campo anterior, así que la explicación
puede ocupar varios renglones.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
def cargar(ruta: Path) -> dict:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"El JSON no es válido (línea {e.lineno}, columna {e.colno}): {e.msg}")


def guardar(banco: dict, ruta: Path) -> None:
    respaldo = ruta.with_suffix(ruta.suffix + ".bak")
    if ruta.is_file():
        respaldo.write_text(ruta.read_text(encoding="utf-8"), encoding="utf-8")
    ruta.write_text(json.dumps(banco, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def resolver_dominio(banco: dict, texto: str) -> str | None:
    """Acepta el id del dominio o su nombre, con o sin tildes."""
    objetivo = sin_tildes(texto.strip())
    for d in banco["dominios"]:
        if sin_tildes(d["id"]) == objetivo or sin_tildes(d["nombre"]) == objetivo:
            return d["id"]
    return None


def siguiente_id(banco: dict, dominio: str) -> str:
    prefijo = re.sub(r"[^a-z]", "", sin_tildes(dominio))[:3] or "pre"
    usados = {p["id"] for p in banco["preguntas"]}
    n = 1
    while f"{prefijo}-{n:02d}" in usados:
        n += 1
    return f"{prefijo}-{n:02d}"


def revisar(banco: dict, p: dict, carpeta_imagenes: Path) -> list[str]:
    """Errores que impiden agregar la pregunta."""
    e = []
    if not p.get("enunciado"):
        e.append("falta el enunciado")
    if len(p.get("opciones", [])) < 2:
        e.append("necesita al menos dos opciones")
    if not p.get("correctas"):
        e.append("no marcaste ninguna opción como correcta")
    if p.get("imagen") and not (carpeta_imagenes / p["imagen"]).is_file():
        e.append(f"la imagen '{p['imagen']}' no existe en {carpeta_imagenes.name}/")
    if p.get("dominio") not in {d["id"] for d in banco["dominios"]}:
        e.append(f"el dominio '{p.get('dominio')}' no está declarado en el banco")
    return e


# --------------------------------------------------------------------------- #
# Modo interactivo
# --------------------------------------------------------------------------- #
def preguntar(texto: str, obligatorio: bool = True) -> str:
    while True:
        v = input(texto).strip()
        if v or not obligatorio:
            return v
        print("  Este campo no puede quedar vacío.")


def modo_interactivo(banco: dict, ruta: Path, carpeta_imagenes: Path) -> int:
    imagenes = sorted(f.name for f in carpeta_imagenes.glob("*")
                      if f.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"})
    agregadas = 0

    while True:
        print("\n" + "─" * 60)
        print("Dominios disponibles:")
        for i, d in enumerate(banco["dominios"], 1):
            n = sum(1 for p in banco["preguntas"] if p["dominio"] == d["id"])
            print(f"  {i}) {d['nombre']}  ({n} preguntas)")

        while True:
            try:
                i = int(preguntar("Dominio (número): "))
                dominio = banco["dominios"][i - 1]["id"]
                break
            except (ValueError, IndexError):
                print("  Escribe uno de los números de la lista.")

        enunciado = preguntar("Enunciado: ")

        if imagenes:
            print("Imágenes disponibles: " + ", ".join(imagenes))
        imagen = preguntar("Imagen (Enter para ninguna): ", obligatorio=False)

        print("Opciones, una por línea. Enter en blanco para terminar.")
        opciones: list[str] = []
        while True:
            o = input(f"  {len(opciones) + 1}) ").strip()
            if not o:
                if len(opciones) >= 2:
                    break
                print("  Necesitas al menos dos opciones.")
                continue
            opciones.append(o)

        while True:
            crudo = preguntar("Número(s) de la(s) opción(es) correcta(s), separados por coma: ")
            try:
                correctas = sorted({int(x) - 1 for x in crudo.replace(" ", "").split(",")})
                if correctas and all(0 <= c < len(opciones) for c in correctas):
                    break
            except ValueError:
                pass
            print("  Escribe números válidos de la lista, por ejemplo: 1,3")

        explicacion = preguntar("Explicación (por qué esa es la correcta): ")
        referencia = preguntar("Referencia (Enter para omitir): ", obligatorio=False)

        p = {
            "id": siguiente_id(banco, dominio),
            "dominio": dominio,
            "enunciado": enunciado,
            "opciones": opciones,
            "correctas": correctas,
            "explicacion": explicacion,
        }
        if imagen:
            p["imagen"] = imagen
        if referencia:
            p["referencia"] = referencia

        errores = revisar(banco, p, carpeta_imagenes)
        if errores:
            print("No se pudo agregar: " + "; ".join(errores))
        else:
            banco["preguntas"].append(p)
            agregadas += 1
            print(f"Agregada como {p['id']}.")

        if preguntar("¿Otra pregunta? (s/n): ", obligatorio=False).lower() not in ("s", "si", "sí", ""):
            break

    if agregadas:
        guardar(banco, ruta)
        plural = "pregunta" if agregadas == 1 else "preguntas"
        print(f"\nGuardada{'' if agregadas == 1 else 's'} {agregadas} {plural} en {ruta.name}. "
              f"El banco tiene {len(banco['preguntas'])}.")
        print(f"Ahora compila: python3 generar_app.py --banco {ruta.name} --salida repaso.html")
    else:
        print("\nNo se agregó ninguna pregunta.")
    return 0


# --------------------------------------------------------------------------- #
# Modo importación
# --------------------------------------------------------------------------- #
def partir_bloques(texto: str) -> list[list[str]]:
    bloques, actual = [], []
    for linea in texto.splitlines():
        if linea.strip():
            actual.append(linea.rstrip())
        elif actual:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def leer_bloque(banco: dict, lineas: list[str]) -> tuple[dict, list[str]]:
    p: dict = {"opciones": [], "correctas": []}
    errores: list[str] = []
    campo: str | None = None

    for linea in lineas:
        m = re.match(r"^\s*([DPIER])\s*:\s*(.*)$", linea)
        if m:
            clave, valor = m.group(1), m.group(2).strip()
            campo = clave
            if clave == "D":
                d = resolver_dominio(banco, valor)
                if d is None:
                    errores.append(f"dominio desconocido: '{valor}'")
                p["dominio"] = d or valor
            elif clave == "P":
                p["enunciado"] = valor
            elif clave == "I":
                p["imagen"] = valor
            elif clave == "E":
                p["explicacion"] = valor
            elif clave == "R":
                p["referencia"] = valor
            continue

        m = re.match(r"^\s*([-*])\s+(.*)$", linea)
        if m:
            campo = "opcion"
            if m.group(1) == "*":
                p["correctas"].append(len(p["opciones"]))
            p["opciones"].append(m.group(2).strip())
            continue

        # Línea sin prefijo: continúa el campo anterior.
        cont = linea.strip()
        if campo == "E":
            p["explicacion"] = (p.get("explicacion", "") + " " + cont).strip()
        elif campo == "P":
            p["enunciado"] = (p.get("enunciado", "") + " " + cont).strip()
        elif campo == "opcion" and p["opciones"]:
            p["opciones"][-1] = (p["opciones"][-1] + " " + cont).strip()
        else:
            errores.append(f"no entiendo la línea: {linea.strip()[:50]}")

    return p, errores


def modo_importar(banco: dict, ruta: Path, origen: Path, carpeta_imagenes: Path) -> int:
    if not origen.is_file():
        sys.exit(f"No encuentro el archivo {origen}.")

    bloques = partir_bloques(origen.read_text(encoding="utf-8"))
    nuevas, rechazadas = [], []

    for i, lineas in enumerate(bloques, 1):
        p, errores = leer_bloque(banco, lineas)
        # El id se asigna contra el banco más las ya aceptadas en esta pasada.
        provisional = {"dominios": banco["dominios"], "preguntas": banco["preguntas"] + nuevas}
        p["id"] = siguiente_id(provisional, p.get("dominio", ""))
        errores += revisar(banco, p, carpeta_imagenes)

        if errores:
            titulo = (p.get("enunciado") or "sin enunciado")[:48]
            rechazadas.append((i, titulo, errores))
        else:
            orden = ["id", "dominio", "enunciado", "imagen", "opciones",
                     "correctas", "explicacion", "referencia"]
            nuevas.append({k: p[k] for k in orden if k in p and p[k] != ""})

    for n, titulo, errores in rechazadas:
        print(f"Bloque {n} descartado ({titulo}…): " + "; ".join(errores))

    if not nuevas:
        print("\nNo se agregó ninguna pregunta.")
        return 1

    banco["preguntas"].extend(nuevas)
    guardar(banco, ruta)

    print(f"\nAgregadas {len(nuevas)} preguntas ({len(rechazadas)} descartadas).")
    print(f"{ruta.name} tiene ahora {len(banco['preguntas'])} preguntas. Copia previa en {ruta.name}.bak")

    por_dominio: dict[str, int] = {}
    for p in banco["preguntas"]:
        por_dominio[p["dominio"]] = por_dominio.get(p["dominio"], 0) + 1
    total = len(banco["preguntas"])
    print("\nReparto actual:")
    for d in banco["dominios"]:
        real = round(por_dominio.get(d["id"], 0) / total * 100)
        peso = d.get("peso")
        extra = f" (examen: {peso} %)" if peso else ""
        print(f"  {d['nombre']}: {por_dominio.get(d['id'], 0)} — {real} %{extra}")

    print(f"\nCompila con: python3 generar_app.py --banco {ruta.name} --salida repaso.html")
    return 0


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Agrega preguntas a un banco de repaso.")
    ap.add_argument("--banco", default="banco_clf.json")
    ap.add_argument("--imagenes", default="imagenes")
    ap.add_argument("--importar", help="archivo de texto con preguntas en lote")
    args = ap.parse_args()

    ruta = RAIZ / args.banco
    carpeta_imagenes = RAIZ / args.imagenes
    if not ruta.is_file():
        sys.exit(f"No encuentro el banco {ruta}.")

    banco = cargar(ruta)
    print(f"{ruta.name}: {len(banco['preguntas'])} preguntas, {len(banco['dominios'])} dominios.")

    if args.importar:
        return modo_importar(banco, ruta, RAIZ / args.importar, carpeta_imagenes)
    return modo_interactivo(banco, ruta, carpeta_imagenes)


if __name__ == "__main__":
    sys.exit(main())
