# Repaso AWS — trivia con diagramas

Versión reescrita del proyecto original de trivia. Python deja de ser el juego y pasa a ser el
**compilador**: valida el banco de preguntas, incrusta los diagramas y produce un archivo HTML
único que se abre en el celular sin internet.

```
banco_clf.json  ─┐
imagenes/*.svg  ─┼─→  generar_app.py  ─→  repaso_clf.html   (un solo archivo, ~79 KB)
plantilla.html  ─┘
```

Hay dos bancos listos:

| Archivo | Certificación | Preguntas | Diagramas |
|---|---|---|---|
| `banco_clf.json` | CLF-C02 · Cloud Practitioner | 41 | 3 |
| `banco_aws.json` | SAA-C03 · Solutions Architect Associate | 16 | 3 |

Dos formatos de salida: un archivo HTML único que se copia al celular, o una carpeta lista para
publicar en GitHub Pages e instalar como app.

## Qué cambió respecto a `trivia3.py`

| Antes | Ahora |
|---|---|
| Compara el texto de la opción con el de la respuesta | Compara índices; el texto puede tener tildes o cambiar |
| Una sola respuesta por pregunta | Una o varias (`"correctas": [0, 2]`) |
| Sin imágenes | Diagrama por pregunta, con visor a pantalla completa y zoom |
| Sin explicación | Explicación y referencia después de cada respuesta |
| Opciones siempre en el mismo orden | Preguntas y opciones se barajan en cada sesión |
| `leadership.json` con claves duplicadas | Historial en el navegador: falladas y últimas 20 sesiones |
| Falla en tiempo de ejecución si el JSON está mal | `--solo-validar` revisa todo el banco antes de compilar |

## Requisitos

Python 3.9 o superior. Sin dependencias externas: solo librería estándar.

## Uso

```bash
# 1. Compilar la app de Cloud Practitioner
python3 generar_app.py --banco banco_clf.json --salida repaso_clf.html

# La de Solutions Architect (valores por defecto)
python3 generar_app.py

# 2. Revisar el banco sin compilar (útil al agregar preguntas)
python3 generar_app.py --solo-validar

# 3. Probarla desde el celular en la misma red wifi
python3 generar_app.py --servir
#    → abre en el navegador del celular la URL que imprime

# 4. Compilar un banco nuevo
python3 generar_app.py --banco banco_dva.json --salida repaso_dva.html
```

## Pasarla al celular

Hay dos caminos. El archivo suelto es inmediato; el sitio instalable es el que se comporta como
una app de verdad.

### Archivo suelto (rápido, sin publicar nada)

1. `python3 generar_app.py --banco banco_clf.json --salida repaso_clf.html`
2. Copia `repaso_clf.html` al teléfono y ábrelo con Chrome.
3. Funciona en modo avión: los diagramas van incrustados.

Limitación real: Chrome trata los archivos locales como un origen sin permisos de
almacenamiento, así que **el historial de falladas no se guarda entre aperturas** y no aparece
la opción de añadir a la pantalla de inicio, que solo existe para direcciones `https://`.

### Sitio instalable en GitHub Pages (recomendado)

```bash
python3 generar_app.py --banco banco_clf.json --pwa sitio
```

Genera la carpeta `sitio/` con todo lo necesario:

| Archivo | Para qué |
|---|---|
| `index.html` | la app completa, con los diagramas incrustados |
| `manifest.json` | nombre, ícono y modo pantalla completa |
| `sw.js` | service worker: guarda todo en caché para usarla sin conexión |
| `icono-192.png`, `icono-512.png` | ícono de la pantalla de inicio |
| `.nojekyll` | evita que GitHub Pages procese los archivos |

Publicación:

1. Crea un repositorio en GitHub, por ejemplo `repaso-aws`.
2. Sube **el contenido** de `sitio/`, no la carpeta: `index.html` tiene que quedar en la raíz.
3. En el repositorio: *Settings* → *Pages* → *Source: Deploy from a branch* → rama `main`,
   carpeta `/ (root)` → *Save*.
4. Espera un par de minutos. Tu URL será `https://<tu-usuario>.github.io/repaso-aws/`.
5. Ábrela en Chrome del celular. Menú de tres puntos → *Instalar aplicación* o *Añadir a la
   pantalla de inicio*.

Con esto ganas ícono propio, pantalla completa sin barra del navegador, funcionamiento sin
conexión desde la segunda visita y, sobre todo, el historial de falladas guardado entre
sesiones.

En el plan gratuito de GitHub, Pages solo funciona con repositorios públicos. El banco de
preguntas queda visible para cualquiera; si eso te molesta, GitLab Pages sí permite sitios
privados.

Para probarlo antes de publicar:

```bash
python3 generar_app.py --banco banco_clf.json --pwa sitio --servir
```

El service worker solo se registra sobre `http://` o `https://`, así que en el archivo suelto
no interfiere.

### Cuando actualices el banco

Vuelve a ejecutar el comando con `--pwa` y sube los archivos otra vez. Cada compilación cambia
el nombre de la caché del service worker, así que el celular descarta la versión vieja sola.
Si aun así ves contenido antiguo, cierra la app y vuelve a abrirla.

## Agregar preguntas

Tres caminos, de más rápido a más manual.

### 1. En lote, desde un archivo de texto (recomendado para muchas)

Escribe las preguntas en un `.txt` con este formato y las importas de una vez:

```
D: seguridad
P: ¿Qué servicio almacena credenciales y las rota automáticamente?
I: responsabilidad-compartida.svg
- AWS Systems Manager Parameter Store
* AWS Secrets Manager
- AWS Key Management Service
- AWS Artifact
E: Secrets Manager guarda secretos cifrados y puede rotarlos solo.
R: AWS Secrets Manager
```

| Prefijo | Significado |
|---|---|
| `D:` | dominio, por id o por nombre |
| `P:` | enunciado |
| `I:` | imagen, opcional; debe existir en `imagenes/` |
| `-` | opción incorrecta |
| `*` | opción correcta (marca varias para respuesta múltiple) |
| `E:` | explicación |
| `R:` | referencia, opcional |

Los bloques se separan con una línea en blanco y las líneas sin prefijo continúan el campo
anterior, así que una explicación puede ocupar varios renglones. `preguntas_nuevas.txt` es un
ejemplo listo para copiar.

```bash
python3 agregar_preguntas.py --banco banco_clf.json --importar preguntas_nuevas.txt
```

El script asigna el id, valida cada bloque y descarta solo los que tengan errores, diciéndote
cuál y por qué. Deja una copia previa en `banco_clf.json.bak` y al final imprime el reparto por
dominio comparado con el peso del examen.

### 2. Una por una, de forma guiada

```bash
python3 agregar_preguntas.py --banco banco_clf.json
```

Te va pidiendo dominio, enunciado, opciones, cuál es la correcta y la explicación, y repite
hasta que respondas `n`.

### 3. Editando el JSON directamente

Cada entrada de `"preguntas"` sigue este esquema:

```json
{
  "id": "seg-05",
  "dominio": "seguridad",
  "enunciado": "Texto de la pregunta.",
  "imagen": "mi-diagrama.svg",
  "opciones": ["Primera", "Segunda", "Tercera", "Cuarta"],
  "correctas": [1],
  "explicacion": "Por qué esa es la respuesta y por qué las otras no.",
  "referencia": "Servicio · concepto"
}
```

Después de editar a mano conviene correr `python3 generar_app.py --solo-validar`.

Reglas que aplica el validador:

- `id` único en todo el banco.
- `dominio` debe existir en la lista `"dominios"` de la raíz.
- `correctas` son **índices** de `opciones`, empezando en 0. Dos o más índices activan el modo
  de respuesta múltiple y la app avisa en pantalla.
- `imagen` es opcional. Si está, el archivo debe existir en `imagenes/`. Formatos: svg, png,
  jpg, webp, gif.
- `explicacion` es opcional para compilar, pero el validador te lo reclama. Para una
  certificación es lo que realmente enseña.

Los diagramas incluidos son SVG hechos a mano. Conviene mantener ese formato: pesan poco,
se ven nítidos al ampliar y se editan como texto. Si usas capturas en PNG, redúcelas antes de
incrustarlas o el archivo final crecerá rápido.

## Cambiar de certificación

Para otra certificación duplica un banco y ajusta `"certificacion"`, `"titulo"`, `"umbral"` y la
lista `"dominios"` con los del examen correspondiente. La plantilla y el compilador no cambian.

El campo `"umbral"` es el porcentaje que la pantalla de resultados marca como aprobación
orientativa: 70 para CLF-C02 y 72 para SAA-C03, según la nota de corte de cada examen sobre la
escala de 100 a 1000.

Al validar, el script imprime el reparto real de preguntas por dominio junto al peso oficial del
examen, para que veas si el banco está desbalanceado:

```
Arquitecturas seguras: 4 preguntas — 25 % (examen real: 30 %)
```

## Límites conocidos

- El umbral que muestra la pantalla de resultados es orientativo. AWS puntúa de 100 a 1000
  (corte en 700 para CLF-C02 y 720 para SAA-C03) y no publica la equivalencia exacta en
  preguntas acertadas.
- No hay marcado de preguntas para revisar después ni navegación hacia atrás dentro de la
  sesión, como sí tiene el examen real.
- El banco de CLF-C02 cubre los cuatro dominios con su peso real, pero 41 preguntas siguen
  siendo pocas frente a las 65 del examen. Conviene ampliarlo hasta unas 150.
- El banco de SAA-C03 tiene solo 16 preguntas y está desbalanceado; es una muestra, no un
  simulacro.
