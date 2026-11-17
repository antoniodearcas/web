"""Lectura de cartas de Esferas desde el archivo público de Mailchimp.

Cada carta se guarda en datos/cartas/NNNN.json con sus versiones es/en,
y sus imágenes se descargan a assets/cartas/ (nombre = hash de la URL).
"""
import hashlib, io, json, os, re, time, unicodedata, urllib.request
from bs4 import BeautifulSoup, NavigableString, Tag

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, 'datos', 'cartas')
IMGS = os.path.join(RAIZ, 'assets', 'cartas')
PLANTILLA = os.path.join(RAIZ, 'datos', 'plantilla.json')
UA = {'User-Agent': 'Mozilla/5.0 (archivo Esferas antoniodearcas.com)'}

PERMITIDAS = {'p', 'br', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'blockquote', 'h2', 'h3', 'sup', 'sub'}
RENOMBRAR = {'i': 'em', 'b': 'strong', 'h1': 'h2', 'h4': 'h3'}
RUIDO_TEXTO = ('si un amigo te ha enviado', 'if a friend sent you', 'if a friend forwarded',
               'comparte esta carta', 'share this letter', 'copyright (c)', 'view this email in your browser',
               'want to change how you receive')
RUIDO_ENLACE = ('eepurl.com', 'list-manage.com/subscribe', 'mailchi.mp/', 'campaign-archive.com',
                'list-manage.com/profile', 'list-manage.com/unsubscribe', 'forward-to-friend')


def get(url, intentos=3):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return (getattr(r, 'status', None) or 200), r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b''
            err = e
        except Exception as e:  # red
            err = e
        time.sleep(2 * (i + 1))
    raise err


def slugify(t):
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode()
    t = re.sub(r'[^a-zA-Z0-9]+', '-', t.lower()).strip('-')
    return re.sub(r'-{2,}', '-', t)[:70].strip('-')


def norm(t):
    t = unicodedata.normalize('NFKC', t or '').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', t).strip()


ES = set('que de la el en y los las se no por con una para es lo como más pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus'.split())
EN = set('the and of to in is that it was for on are with as i his they be at one have this from or had by but some what there we can out other were all your when up use how said an each she which do their if will way about many then them would like so these her him has more could go come did my no not you me'.split())


def idioma(texto):
    w = re.findall(r"[a-záéíóúñü']+", texto.lower())
    es = sum(x in ES for x in w); en = sum(x in EN for x in w)
    return 'es' if es >= en else 'en'


def limpiar(nodo):
    """Devuelve HTML semántico limpio de un bloque de texto de Mailchimp."""
    soup = BeautifulSoup(str(nodo), 'html.parser')
    for t in soup.find_all(True):
        if t.name in RENOMBRAR:
            t.name = RENOMBRAR[t.name]
    for t in list(soup.find_all(True)):
        if t.name not in PERMITIDAS:
            t.unwrap()
            continue
        href = t.get('href') if t.name == 'a' else None
        t.attrs = {}
        if href:
            t['href'] = href
    html = str(soup)
    html = html.replace('\xa0', ' ')
    # párrafos vacíos (separadores de Mailchimp)
    html = re.sub(r'<p>(\s|<br/?>)*</p>', '', html)
    html = re.sub(r'<(em|strong)>\s*</\1>', '', html)
    html = re.sub(r'</em>(\s*)<em>', r'\1', html)
    html = re.sub(r'</strong>(\s*)<strong>', r'\1', html)
    html = re.sub(r'(<br/?>\s*){3,}', '<br/><br/>', html)
    html = re.sub(r'<p>\s*(<br/?>\s*)+', '<p>', html)
    html = re.sub(r'(\s*<br/?>)+\s*</p>', '</p>', html)
    html = re.sub(r'\s+', ' ', html).strip()
    # texto suelto sin <p>
    if html and not html.startswith('<'):
        html = '<p>' + html + '</p>'
    return html


def leer_carta(html, url=''):
    """Convierte la página de archivo de una campaña en una lista de bloques."""
    soup = BeautifulSoup(html, 'html.parser')
    og = soup.find('meta', property='og:title')
    titulo_full = norm(og['content'] if og else (soup.title.string if soup.title else ''))
    m = re.match(r'^(\d+)\.\s*(.*)$', titulo_full)
    num = int(m.group(1)) if m else None
    titulo = m.group(2).strip() if m else titulo_full
    cuerpo = soup.find(id='bodyTable') or soup.body
    excluir = cuerpo.select('.mceSectionHeader, .mceSectionFooter, .mceFooterSection, .mceSocialFollowBlock, '
                            '.mcnFollowContent, #templateFooter, .footerContainer, .mcnPreviewText')
    excl = set(id(x) for x in excluir)

    def excluido(el):
        for p in el.parents:
            if id(p) in excl:
                return True
        return False

    bloques = []
    sel = 'img, div.mceText, div.mcnTextContent, td.mcnTextContent, a.mceButtonLink, a.mcnButton'
    for el in cuerpo.select(sel):
        if excluido(el):
            continue
        # evitar contar textos anidados dos veces
        if el.name in ('div', 'td') and el.find_parent(['div', 'td'], class_=['mceText', 'mcnTextContent']):
            continue
        if el.name == 'img':
            src = el.get('src', '')
            clases = ' '.join(el.get('class', []))
            if 'mceSocialFollowImage' in clases or 'mceLogo' in clases or 'cdn-images.mailchimp.com' in src:
                continue
            if not src.startswith(('http', 'file:')):
                continue
            w = el.get('width')
            if w and w.isdigit() and int(w) < 120:
                continue
            enlace = el.find_parent('a')
            href = enlace.get('href', '') if enlace else ''
            bloques.append({'t': 'img', 'src': src, 'href': href})
        elif el.name == 'a':
            texto = norm(el.get_text())
            href = el.get('href', '')
            if not texto or any(r in href for r in RUIDO_ENLACE) or any(r in texto.lower() for r in RUIDO_TEXTO):
                continue
            bloques.append({'t': 'boton', 'texto': texto, 'href': href})
        else:
            texto = norm(el.get_text(' '))
            if not texto:
                continue
            bajo = texto.lower()
            if any(bajo.startswith(r) or r in bajo[:80] for r in RUIDO_TEXTO):
                continue
            h = limpiar(el)
            if not h:
                continue
            bloques.append({'t': 'texto', 'html': h, 'plano': texto})

    # Identificar título, intro y firma
    tnorm = norm(titulo_full).lower()
    pos_titulo = None
    for i, b in enumerate(bloques):
        if b['t'] != 'texto':
            continue
        p = b['plano'].lower()
        if p == tnorm or p == norm(titulo).lower() or (len(p) < len(tnorm) + 4 and p.startswith(tnorm[:max(6, len(tnorm) - 3)])):
            pos_titulo = i
            break
    if pos_titulo is not None:
        bloques.pop(pos_titulo)
        for b in bloques[:pos_titulo]:
            if b['t'] == 'texto':
                b['t'] = 'intro'
    for b in bloques:
        if b['t'] == 'texto' and re.match(r'^(con todo mi amor|con amor|with all my love|with love|un abrazo)', b['plano'].lower()):
            b['t'] = 'firma'
    texto_total = ' '.join(b.get('plano', '') for b in bloques)
    pre = soup.select_one('.mcnPreviewText')
    subtitulo = norm(re.sub(r'[͏‌­]', '', pre.get_text())) if pre else ''
    return {'num': num, 'titulo': titulo, 'titulo_completo': titulo_full, 'url': url,
            'subtitulo': subtitulo, 'idioma': idioma(texto_total), 'bloques': bloques}


def aplicar_plantilla(carta, plantilla):
    """Quita imágenes y textos que se repiten en muchas cartas (cabecera, pie, invitaciones fijas)."""
    imgs = set(plantilla.get('imagenes', []))
    textos = set(plantilla.get('textos', []))
    fuera = []
    for b in carta['bloques']:
        if b['t'] == 'img' and os.path.basename(b['src']) in imgs:
            continue
        if b['t'] in ('texto', 'intro') and huella(b['plano']) in textos:
            continue
        fuera.append(b)
    # la cabecera enlazada a la web antigua nunca es parte de la carta
    fuera = [b for b in fuera if not (b['t'] == 'img' and re.match(r'^https?://(www\.)?(astrofonda|antoniodearcas)\.com/?$', b.get('href', '')))]
    carta['bloques'] = fuera
    return carta


def huella(texto):
    return hashlib.sha1(norm(texto).lower().encode()).hexdigest()[:16]


META_IMGS = os.path.join(RAIZ, 'datos', 'imagenes.json')
_meta = None


def _meta_imgs():
    global _meta
    if _meta is None:
        _meta = json.load(open(META_IMGS)) if os.path.exists(META_IMGS) else {}
    return _meta


def descargar_imagen(src):
    """Descarga y optimiza una imagen; devuelve (ruta relativa, ancho, alto).
    Si el contenido ya existe (misma foto con otra URL), reutiliza el archivo."""
    from PIL import Image, ImageOps
    os.makedirs(IMGS, exist_ok=True)
    meta = _meta_imgs()
    if src in meta and os.path.exists(os.path.join(RAIZ, meta[src]['ruta'])):
        d = meta[src]
        return d['ruta'], d['w'], d['h']
    estado, datos = get(src)
    if estado != 200 or not datos:
        return None, 0, 0
    im = Image.open(io.BytesIO(datos))
    if src.lower().endswith('.gif'):
        ext, salida = '.gif', datos
        w, h = im.size
    else:
        im = ImageOps.exif_transpose(im)
        if im.width > 1400:
            im = im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS)
        w, h = im.size
        o = io.BytesIO()
        if im.mode in ('RGBA', 'LA', 'P') and _tiene_transparencia(im):
            ext = '.png'
            im.save(o, format='PNG', optimize=True)
        else:
            ext = '.jpg'
            im.convert('RGB').save(o, format='JPEG', quality=76, optimize=True, progressive=True)
        salida = o.getvalue()
    nombre = hashlib.sha1(salida).hexdigest()[:14] + ext
    destino = os.path.join(IMGS, nombre)
    if not os.path.exists(destino):
        with open(destino, 'wb') as f:
            f.write(salida)
    ruta = 'assets/cartas/' + nombre
    meta[src] = {'ruta': ruta, 'w': w, 'h': h, 'src': src}
    with open(META_IMGS, 'w') as f:
        json.dump(meta, f, indent=0)
    return ruta, w, h


def _tiene_transparencia(im):
    if im.mode == 'P':
        return 'transparency' in im.info
    alfa = im.getchannel('A')
    return alfa.getextrema()[0] < 250


def ruta_datos(num):
    return os.path.join(DATOS, '%04d.json' % num)


def cargar(num):
    p = ruta_datos(num)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return None


def guardar(d):
    os.makedirs(DATOS, exist_ok=True)
    with open(ruta_datos(d['num']), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write('\n')


def cargar_todas():
    out = []
    if not os.path.isdir(DATOS):
        return out
    for n in sorted(os.listdir(DATOS)):
        if n.endswith('.json'):
            with open(os.path.join(DATOS, n), encoding='utf-8') as f:
                out.append(json.load(f))
    return out
