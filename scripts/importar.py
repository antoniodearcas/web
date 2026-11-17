"""Importa cartas de Esferas desde el archivo público de Mailchimp.

  python3 scripts/importar.py --todo [--pendientes-desde N]   # todo el archivo (una vez)
  python3 scripts/importar.py --nuevas                        # lo último del RSS (cada semana)

--nuevas escribe en datos/nuevas.txt los números añadidos como pendientes.
"""
import argparse, collections, email.utils, json, os, re, sys
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esferas import *  # noqa

FEED = 'https://us9.campaign-archive.com/feed?u=b4d2c5678ab83f29b90084eb3&id=614fdee5a6'
FECHAS = os.path.join(RAIZ, 'datos', 'fechas.json')


def extracto(bloques, n=190):
    for tipo in ('intro', 'texto'):
        for b in bloques:
            if b['t'] == tipo and len(b.get('plano', '')) > 30:
                t = b['plano']
                if len(t) <= n:
                    return t
                corte = t[:n].rsplit(' ', 1)[0].rstrip(',;:')
                return corte + '…'
    return ''


def preparar(carta, plantilla):
    carta = aplicar_plantilla(carta, plantilla)
    bloques = []
    for b in carta['bloques']:
        if b['t'] == 'img':
            ruta, w, h = descargar_imagen(b['src'])
            if not ruta:
                continue
            nb = {'t': 'img', 'ruta': ruta, 'w': w, 'h': h}
            if b.get('href') and not re.search(r'(astrofonda|antoniodearcas)\.com/?$', b['href']) and 'mcusercontent' not in b['href']:
                nb['href'] = b['href']
            bloques.append(nb)
        else:
            bloques.append(b)
    portada = next((b for b in bloques if b['t'] == 'img'), None)
    return {
        'titulo': carta['titulo'],
        'slug': '%d-%s' % (carta['num'], slugify(carta['titulo'])),
        'origen': carta['url'],
        'portada': {k: portada[k] for k in ('ruta', 'w', 'h')} if portada else None,
        'subtitulo': carta.get('subtitulo', ''),
        'extracto': extracto(bloques),
        'bloques': bloques,
    }


def leer_url(url):
    estado, html = get(url)
    if estado != 200 or b'Page Not Found' in html[:4000]:
        return None
    c = leer_carta(html.decode('utf-8', 'replace'), url)
    return c if c['num'] else None


def calcular_plantilla(cartas):
    imgs, textos = collections.defaultdict(set), collections.defaultdict(set)
    for c in cartas:
        for b in c['bloques']:
            if b['t'] == 'img':
                imgs[os.path.basename(b['src'])].add(c['num'])
            elif b['t'] in ('texto', 'intro'):
                textos[huella(b['plano'])].add(c['num'])
    return {'imagenes': sorted(k for k, v in imgs.items() if len(v) >= 4),
            'textos': sorted(k for k, v in textos.items() if len(v) >= 4)}


def fechas():
    if os.path.exists(FECHAS):
        with open(FECHAS) as f:
            return json.load(f)
    return {}


def todo(args):
    vistas, fallos = [], 0
    for n in range(1, 400):
        hallada = False
        for suf in ('', '-en'):
            for pref in ('antoniodearcas', 'astrofonda'):
                c = leer_url('https://mailchi.mp/%s/%d%s' % (pref, n, suf))
                if c:
                    c['suf'] = suf
                    vistas.append(c)
                    hallada = True
                    print('ok', n, suf, c['idioma'], c['titulo'], flush=True)
                    break
        fallos = 0 if hallada else fallos + 1
        if n > 150 and fallos > 12:
            break
    plantilla = calcular_plantilla(vistas)
    os.makedirs(os.path.dirname(PLANTILLA), exist_ok=True)
    with open(PLANTILLA, 'w') as f:
        json.dump(plantilla, f, indent=1)
    fs = fechas()
    por_num = collections.defaultdict(dict)
    for c in vistas:
        lang = 'en' if c['suf'] == '-en' else c['idioma']
        if lang in por_num[c['num']]:
            lang = 'en' if lang == 'es' else 'es'
        por_num[c['num']][lang] = c
    for num, langs in sorted(por_num.items()):
        d = cargar(num) or {'num': num}
        d['enviada'] = fs.get(str(num), d.get('enviada'))
        pend = args.pendientes_desde and num >= args.pendientes_desde
        d.setdefault('estado', 'pendiente' if pend else 'publicada')
        for lang, c in langs.items():
            d[lang] = preparar(c, plantilla)
        guardar(d)
        print('guardada', num, sorted(langs), flush=True)


def nuevas(args):
    with open(PLANTILLA) as f:
        plantilla = json.load(f)
    estado, xml = get(FEED)
    canal = ET.fromstring(xml).find('channel')
    fs = fechas()
    añadidas = []
    for it in canal.findall('item'):
        url = it.findtext('link')
        fecha = email.utils.parsedate_to_datetime(it.findtext('pubDate')).astimezone().date().isoformat()
        m = re.search(r'/(\d+)(-en)?/?$', url or '')
        if not m:
            continue
        num = int(m.group(1))
        d = cargar(num)
        c = leer_url(url)
        if not c:
            continue
        lang = 'en' if m.group(2) else c['idioma']
        if d and lang in d:
            continue
        nueva = d is None
        d = d or {'num': num, 'estado': 'pendiente'}
        d.setdefault('enviada', fecha)
        d[lang] = preparar(c, plantilla)
        guardar(d)
        fs.setdefault(str(num), fecha)
        if nueva:
            añadidas.append(num)
        print('nueva', num, lang, c['titulo'], flush=True)
    with open(FECHAS, 'w') as f:
        json.dump(dict(sorted(fs.items(), key=lambda x: int(x[0]))), f, indent=1)
    with open(os.path.join(RAIZ, 'datos', 'nuevas.txt'), 'w') as f:
        f.write('\n'.join(map(str, sorted(set(añadidas)))))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--todo', action='store_true')
    ap.add_argument('--nuevas', action='store_true')
    ap.add_argument('--pendientes-desde', type=int)
    a = ap.parse_args()
    todo(a) if a.todo else nuevas(a)
