#!/usr/bin/env python3
"""
Compilador del banco de preguntas a una app HTML autocontenida.

Lee banco_aws.json + la carpeta imagenes/, incrusta cada diagrama como data URI
dentro de plantilla.html y escribe un único archivo que funciona sin internet,
apto para copiar al celular.

Uso:
    python3 generar_app.py
    python3 generar_app.py --banco otro_banco.json --salida repaso_dva.html
    python3 generar_app.py --solo-validar
    python3 generar_app.py --servir          # servidor local para probar desde el celular
    python3 generar_app.py --pwa sitio       # sitio instalable para GitHub Pages
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import socket
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MARCADOR = "/*__DATOS_BANCO__*/{}"
MARCA_CABECERA = "<!--__CABECERA_PWA__-->"
MARCA_SW = "<!--__REGISTRO_SW__-->"
FORMATOS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ErrorDeBanco(Exception):
    """El banco de preguntas no cumple el esquema."""


# --------------------------------------------------------------------------- #
# Validación
# --------------------------------------------------------------------------- #
def validar(banco: dict, carpeta_imagenes: Path) -> list[str]:
    """Devuelve la lista de avisos. Lanza ErrorDeBanco si algo impide compilar."""
    fallos: list[str] = []
    avisos: list[str] = []

    for campo in ("certificacion", "titulo", "dominios", "preguntas"):
        if campo not in banco:
            fallos.append(f"Falta el campo obligatorio '{campo}' en la raíz del banco.")
    if fallos:
        raise ErrorDeBanco("\n".join(fallos))

    ids_dominio = {d["id"] for d in banco["dominios"]}
    vistos: set[str] = set()

    for i, p in enumerate(banco["preguntas"], start=1):
        etq = p.get("id") or f"pregunta #{i}"

        for campo in ("id", "dominio", "enunciado", "opciones", "correctas"):
            if campo not in p:
                fallos.append(f"[{etq}] falta el campo '{campo}'.")
        if any(c not in p for c in ("opciones", "correctas")):
            continue

        if p.get("id") in vistos:
            fallos.append(f"[{etq}] el id está repetido.")
        vistos.add(p.get("id"))

        if p.get("dominio") not in ids_dominio:
            fallos.append(f"[{etq}] el dominio '{p.get('dominio')}' no está declarado.")

        opciones = p["opciones"]
        if not isinstance(opciones, list) or len(opciones) < 2:
            fallos.append(f"[{etq}] necesita al menos dos opciones.")
            continue

        correctas = p["correctas"]
        if not isinstance(correctas, list) or not correctas:
            fallos.append(f"[{etq}] 'correctas' debe ser una lista con al menos un índice.")
            continue
        if len(set(correctas)) != len(correctas):
            fallos.append(f"[{etq}] hay índices repetidos en 'correctas'.")
        fuera = [c for c in correctas if not isinstance(c, int) or not 0 <= c < len(opciones)]
        if fuera:
            fallos.append(f"[{etq}] índices fuera de rango en 'correctas': {fuera}.")

        if not p.get("explicacion"):
            avisos.append(f"[{etq}] sin explicación. En una certificación es lo que más enseña.")

        nombre = p.get("imagen")
        if nombre:
            ruta = carpeta_imagenes / nombre
            if not ruta.is_file():
                fallos.append(f"[{etq}] no encuentro la imagen '{nombre}' en {carpeta_imagenes}.")
            elif ruta.suffix.lower() not in FORMATOS:
                fallos.append(f"[{etq}] formato de imagen no soportado: '{ruta.suffix}'.")

    if fallos:
        raise ErrorDeBanco("\n".join(fallos))
    return avisos


# --------------------------------------------------------------------------- #
# Compilación
# --------------------------------------------------------------------------- #
def a_data_uri(ruta: Path) -> str:
    tipo, _ = mimetypes.guess_type(ruta.name)
    if ruta.suffix.lower() == ".svg":
        tipo = "image/svg+xml"
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return f"data:{tipo or 'application/octet-stream'};base64,{datos}"


def incrustar_imagenes(banco: dict, carpeta_imagenes: Path) -> tuple[dict, int]:
    """Añade 'imagen_datos' a cada pregunta con imagen. Reutiliza archivos repetidos."""
    cache: dict[str, str] = {}
    incrustadas = 0
    for p in banco["preguntas"]:
        nombre = p.get("imagen")
        if not nombre:
            continue
        if nombre not in cache:
            cache[nombre] = a_data_uri(carpeta_imagenes / nombre)
            incrustadas += 1
        p["imagen_datos"] = cache[nombre]
    return banco, incrustadas


def compilar(banco: dict, plantilla: Path, salida: Path,
             cabecera: str = "", registro_sw: str = "") -> None:
    html = plantilla.read_text(encoding="utf-8")
    if MARCADOR not in html:
        raise ErrorDeBanco(
            f"La plantilla {plantilla.name} no contiene el marcador {MARCADOR}."
        )
    datos = json.dumps(banco, ensure_ascii=False, separators=(",", ":"))
    # Evita que un '</script>' dentro de un texto corte el bloque del navegador.
    datos = datos.replace("</", "<\\/")
    html = html.replace(MARCADOR, datos)
    html = html.replace(MARCA_CABECERA, cabecera)
    html = html.replace(MARCA_SW, registro_sw)
    salida.write_text(html, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Sitio instalable (PWA) para GitHub Pages
# --------------------------------------------------------------------------- #
def generar_iconos(codigo: str, carpeta: Path) -> list[str]:
    """Ícono cuadrado con el código de la certificación. Devuelve los nombres creados."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  aviso: sin Pillow no se generan íconos; instala con "
              "'pip install Pillow' si quieres el ícono en la pantalla de inicio.")
        return []

    fuentes = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    nombres = []
    for lado in (192, 512):
        img = Image.new("RGB", (lado, lado), "#3F6EA6")
        d = ImageDraw.Draw(img)
        # Marco interior, dentro de la zona segura del ícono adaptable de Android.
        m = int(lado * 0.26)
        d.rounded_rectangle([m, m, lado - m, lado - m], radius=int(lado * 0.05),
                            outline="#FFFFFF", width=max(2, int(lado * 0.018)))
        fuente = None
        for ruta in fuentes:
            if Path(ruta).is_file():
                fuente = ImageFont.truetype(ruta, int(lado * 0.14))
                break
        texto = (codigo or "AWS").split("-")[0][:4]
        if fuente:
            caja = d.textbbox((0, 0), texto, font=fuente)
            d.text(((lado - caja[2] + caja[0]) / 2, (lado - caja[3] + caja[1]) / 2 - caja[1]),
                   texto, font=fuente, fill="#FFFFFF")
        nombre = f"icono-{lado}.png"
        img.save(carpeta / nombre, "PNG")
        nombres.append(nombre)
    return nombres


def generar_pwa(banco: dict, plantilla: Path, carpeta: Path, version: str) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    codigo = banco.get("certificacion", "AWS")
    iconos = generar_iconos(codigo, carpeta)

    manifiesto = {
        "name": f"Repaso {banco.get('titulo', 'AWS')}",
        "short_name": codigo,
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#F5F6F4",
        "theme_color": "#F5F6F4",
        "lang": "es",
        "icons": [
            {"src": f"./{n}", "sizes": f"{n.split('-')[1].split('.')[0]}x{n.split('-')[1].split('.')[0]}",
             "type": "image/png", "purpose": "any maskable"}
            for n in iconos
        ],
    }
    (carpeta / "manifest.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archivos = ["./", "./index.html", "./manifest.json"] + [f"./{n}" for n in iconos]
    sw = f'''/* Service worker generado por generar_app.py — no editar a mano. */
const CACHE = "repaso-{codigo.lower()}-{version}";
const ARCHIVOS = {json.dumps(archivos)};

self.addEventListener("install", (e) => {{
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
}});

self.addEventListener("activate", (e) => {{
  e.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
}});

self.addEventListener("fetch", (e) => {{
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((r) => r || fetch(e.request).catch(() => caches.match("./index.html")))
  );
}});
'''
    (carpeta / "sw.js").write_text(sw, encoding="utf-8")

    cabecera = ('<link rel="manifest" href="./manifest.json">'
                + (f'\n<link rel="apple-touch-icon" href="./{iconos[0]}">' if iconos else ""))
    registro = ('<script>\n'
                'if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {\n'
                '  window.addEventListener("load", () => {\n'
                '    navigator.serviceWorker.register("sw.js").catch(() => {});\n'
                '  });\n'
                '}\n'
                '</script>')

    compilar(banco, plantilla, carpeta / "index.html", cabecera, registro)
    (carpeta / ".nojekyll").write_text("", encoding="utf-8")

    total = sum(f.stat().st_size for f in carpeta.iterdir() if f.is_file())
    print(f"\nSitio instalable en {carpeta.name}/ "
          f"({len(list(carpeta.iterdir()))} archivos, {total / 1024:.0f} KB):")
    for f in sorted(carpeta.iterdir()):
        print(f"  {f.name}")


# --------------------------------------------------------------------------- #
# Servidor de prueba
# --------------------------------------------------------------------------- #
def servir(directorio: Path, archivo: str, puerto: int = 8000) -> None:
    import http.server
    import functools

    manejador = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(directorio)
    )
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        ip = "127.0.0.1"

    print(f"\nAbre en el celular (misma red wifi): http://{ip}:{puerto}/{archivo}")
    print("Ctrl + C para detener.\n")
    with http.server.ThreadingHTTPServer(("0.0.0.0", puerto), manejador) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Compila el banco de preguntas a una app HTML.")
    ap.add_argument("--banco", default="banco_aws.json")
    ap.add_argument("--plantilla", default="plantilla.html")
    ap.add_argument("--imagenes", default="imagenes")
    ap.add_argument("--salida", default="repaso_aws.html")
    ap.add_argument("--solo-validar", action="store_true")
    ap.add_argument("--pwa", metavar="CARPETA",
                    help="genera un sitio instalable (index.html, manifest.json, sw.js, íconos)")
    ap.add_argument("--servir", action="store_true")
    ap.add_argument("--puerto", type=int, default=8000)
    args = ap.parse_args()

    ruta_banco = RAIZ / args.banco
    carpeta_imagenes = RAIZ / args.imagenes
    salida = RAIZ / args.salida

    if not ruta_banco.is_file():
        print(f"No encuentro el banco: {ruta_banco}", file=sys.stderr)
        return 1

    try:
        banco = json.loads(ruta_banco.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"El JSON no es válido (línea {e.lineno}, columna {e.colno}): {e.msg}", file=sys.stderr)
        return 1

    try:
        avisos = validar(banco, carpeta_imagenes)
    except ErrorDeBanco as e:
        print("El banco tiene errores:\n", file=sys.stderr)
        print(e, file=sys.stderr)
        return 1

    total = len(banco["preguntas"])
    con_imagen = sum(1 for p in banco["preguntas"] if p.get("imagen"))
    print(f"Banco válido: {total} preguntas, {len(banco['dominios'])} dominios, {con_imagen} con diagrama.")

    por_dominio: dict[str, int] = {}
    for p in banco["preguntas"]:
        por_dominio[p["dominio"]] = por_dominio.get(p["dominio"], 0) + 1
    for d in banco["dominios"]:
        peso = d.get("peso")
        real = round(por_dominio.get(d["id"], 0) / total * 100)
        extra = f" (examen real: {peso} %)" if peso else ""
        print(f"  {d['nombre']}: {por_dominio.get(d['id'], 0)} preguntas — {real} %{extra}")

    for a in avisos:
        print(f"  aviso: {a}")

    if args.solo_validar:
        return 0

    banco, incrustadas = incrustar_imagenes(banco, carpeta_imagenes)

    if args.pwa:
        carpeta = RAIZ / args.pwa
        version = datetime.now().strftime("%Y%m%d%H%M")
        generar_pwa(banco, RAIZ / args.plantilla, carpeta, version)
        print(f"{incrustadas} diagramas incrustados. Sube el contenido de "
              f"{carpeta.name}/ a la rama de GitHub Pages.")
        if args.servir:
            servir(carpeta, "index.html", args.puerto)
        return 0

    compilar(banco, RAIZ / args.plantilla, salida)
    peso_kb = salida.stat().st_size / 1024
    print(f"\nGenerado {salida.name} ({peso_kb:.0f} KB, {incrustadas} diagramas incrustados).")

    if args.servir:
        servir(RAIZ, salida.name, args.puerto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
