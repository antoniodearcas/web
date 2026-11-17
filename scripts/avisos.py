"""Avisos de aprobación: una issue de GitHub por cada carta pendiente.

GitHub envía la issue por email a Antonio. Si responde «sí» al email (o comenta
«sí» en la issue), la carta queda aprobada y se publica DIAS días después de su
envío. Si responde «no», se descarta.

  python3 scripts/avisos.py abrir            # abre avisos de cartas pendientes sin aviso
  python3 scripts/avisos.py responder N TXT  # aplica la respuesta a la carta N
"""
import datetime, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esferas import cargar, cargar_todas, guardar
from construir import fecha

DIAS = 14
REPO = os.environ.get('GITHUB_REPOSITORY', 'antoniodearcas/web')
RAMA = os.environ.get('GITHUB_REF_NAME', 'main')
SI = re.compile(r'^\s*(s[ií]|yes|ok|vale|adelante|s[uú]bela|subir|publ[ií]cala|👍|✅)\b', re.I)
NO = re.compile(r'^\s*(no|descarta|desc[aá]rtala|mejor no)\b', re.I)


def fecha_publicacion(c):
    hoy = datetime.date.today()
    base = datetime.date.fromisoformat(c['enviada']) if c.get('enviada') else hoy
    return max(base + datetime.timedelta(days=DIAS), hoy).isoformat()


def gh(*args, entrada=None):
    return subprocess.run(['gh', *args], input=entrada, text=True, capture_output=True, check=True).stdout.strip()


def abrir():
    gh('label', 'create', 'carta', '--color', '5c7484', '--description', 'Carta de Esferas pendiente de subir a la web', '--force')
    for c in cargar_todas():
        if c.get('estado') != 'pendiente' or c.get('aviso'):
            continue
        v = c.get('es') or c.get('en')
        titulo = f"¿Subimos la carta {c['num']} a la web? · {v['titulo']}"
        img = ''
        if v.get('portada'):
            img = f"![{v['titulo']}](https://raw.githubusercontent.com/{REPO}/{RAMA}/{v['portada']['ruta']})\n\n"
        sub = v.get('subtitulo') or ''
        ext = v.get('extracto') or ''
        idiomas = ' y '.join(x for x, k in (('español', 'es'), ('inglés', 'en')) if k in c)
        cuando = fecha(fecha_publicacion(c), 'es')
        cuerpo = (f"{img}## {c['num']}. {v['titulo']}\n\n"
                  + (f"*{sub}*\n\n" if sub else '')
                  + (f"> {ext}\n\n" if ext else '')
                  + f"Versiones: {idiomas}. [Leer la carta original]({v.get('origen', '')})\n\n"
                  "---\n\n"
                  f"### Para subirla, responde **sí** a este email\n\n"
                  f"Se publicará en antoniodearcas.com/cartas el **{cuando}**, con las imágenes tal y como salieron en el email.\n\n"
                  "Si prefieres que esta no salga, responde **no**. Si no respondes, se queda guardada sin publicar.")
        url = gh('issue', 'create', '--title', titulo, '--label', 'carta', '--body-file', '-', entrada=cuerpo)
        c['aviso'] = int(url.rstrip('/').split('/')[-1])
        guardar(c)
        print('aviso', c['num'], url)


def responder(num, texto):
    c = cargar(int(num))
    if not c:
        return 'sin-carta'
    if SI.search(texto):
        c['estado'] = 'aprobada'
        c['publicar'] = fecha_publicacion(c)
        guardar(c)
        return 'Hecho. La carta %d se publicará el %s.' % (c['num'], fecha(c['publicar'], 'es'))
    if NO.search(texto):
        c['estado'] = 'descartada'
        guardar(c)
        return 'De acuerdo, la carta %d no se subirá a la web. Si cambias de idea, responde «sí».' % c['num']
    return ''


if __name__ == '__main__':
    if sys.argv[1] == 'abrir':
        abrir()
    else:
        print(responder(sys.argv[2], sys.argv[3]))
