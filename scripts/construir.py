"""Genera las páginas del archivo de cartas a partir de datos/cartas/*.json.

  python3 scripts/construir.py [--hoy AAAA-MM-DD] [--todas]

Solo se publican las cartas con estado "publicada", o "aprobada" cuya fecha
"publicar" ya ha llegado. --todas genera también las pendientes (para revisar).
"""
import argparse, datetime, html, json, os, re, shutil, sys
from email.utils import format_datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esferas import RAIZ, cargar_todas

V = '5'  # versión de css/js
SITIO = 'https://antoniodearcas.com'
AUTOR = {'@type': 'Person', '@id': SITIO + '/#antonio', 'name': 'Antonio de Arcas', 'url': SITIO + '/',
         'sameAs': ['https://instagram.com/adearcas', 'https://www.youtube.com/@adearcas']}
# Páginas fijas que entran en el sitemap (las de redirección llevan noindex y no van)
FIJAS = ['/', '/sobre/', '/en/about/', '/ofertas/', '/acompanamiento/', '/musica/', '/conciertos/', '/privacidad/']
HOOK = 'https://hook.us2.make.com/xwe37csw8iec3acyn64el68eee1eo6qp'
MESES = {'es': 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(),
         'en': 'January February March April May June July August September October November December'.split()}

T = {
    'es': {
        'base': '/cartas/', 'otra': '/en/letters/', 'lang': 'es', 'nombre': 'Cartas',
        'titulo_indice': 'Archivo de cartas', 'desc_indice': 'Todas las cartas de Esferas, la carta que escribo cada domingo.',
        'intro_indice': 'Una carta cada domingo, escrita desde la brecha en nuestra alma que parece separarnos del amor de Dios. Aquí puedes leer las que ya han salido.',
        'recibir': 'Recibe la próxima por email',
        'volver': 'Todas las cartas', 'anterior': 'Anterior', 'siguiente': 'Siguiente',
        'nav': [('/', 'Esferas'), ('/cartas/', 'Archivo de cartas'), ('/ofertas/', 'Ofertas'), ('/musica/', 'Música'), ('/sobre/', 'Sobre mí')],
        'alta_t': 'Recibe la próxima carta',
        'alta_p': 'Cada domingo, una carta como esta en tu correo. Gratis.',
        'email': 'Email', 'acepto': 'Acepto la <a href="/privacidad/">política de privacidad</a>', 'boton': 'Me uno',
        'idioma': 'Español', 'privacidad': 'Privacidad',
        'm_email': 'Escribe un email válido.', 'm_priv': 'Para unirte, acepta la política de privacidad.',
        'm_env': 'Enviando...', 'm_ok': 'Gracias por unirte. Pronto te llegará mi carta de bienvenida.',
        'm_err': 'No se ha podido enviar. Inténtalo de nuevo en un momento.',
        'serie': 'Carta de Esferas por Antonio de Arcas', 'feed': 'Esferas · Cartas de Antonio de Arcas',
        'menu_a': 'Abrir menú', 'menu_c': 'Cerrar menú', 'inicio': 'Antonio de Arcas, inicio', 'secciones': 'Secciones',
    },
    'en': {
        'base': '/en/letters/', 'otra': '/cartas/', 'lang': 'en', 'nombre': 'Letters',
        'titulo_indice': 'Letter archive', 'desc_indice': 'Every letter of Esferas, the letter I write each Sunday.',
        'intro_indice': 'A letter every Sunday, written from the gap in our soul that seems to separate us from the love of God. Here are the ones already sent.',
        'recibir': 'Get the next one by email',
        'volver': 'All letters', 'anterior': 'Previous', 'siguiente': 'Next',
        'nav': [('/', 'Esferas'), ('/en/letters/', 'Letter archive'), ('/ofertas/', 'Offers'), ('/musica/', 'Music'), ('/en/about/', 'About')],
        'alta_t': 'Receive the next letter',
        'alta_p': 'Every Sunday, a letter like this one in your inbox. Free.',
        'email': 'Email', 'acepto': 'I accept the <a href="/privacidad/">privacy policy</a>', 'boton': 'Join',
        'idioma': 'English', 'privacidad': 'Privacy',
        'm_email': 'Please enter a valid email.', 'm_priv': 'To join, please accept the privacy policy.',
        'm_env': 'Sending...', 'm_ok': 'Thank you for joining. My welcome letter is on its way.',
        'm_err': 'It could not be sent. Please try again in a moment.',
        'serie': 'An Esferas letter by Antonio de Arcas', 'feed': 'Esferas · Letters by Antonio de Arcas',
        'menu_a': 'Open menu', 'menu_c': 'Close menu', 'inicio': 'Antonio de Arcas, home', 'secciones': 'Sections',
    },
}

REDES = ('<span class="redes"><a class="red" href="https://instagram.com/adearcas" target="_blank" rel="noopener" aria-label="Instagram"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="17.3" cy="6.7" r="1.1" fill="currentColor"/></svg></a>'
         '<a class="red" href="https://www.youtube.com/@adearcas" target="_blank" rel="noopener" aria-label="YouTube"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="5.5" width="19" height="13" rx="4" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 9.2v5.6l4.8-2.8z" fill="currentColor"/></svg></a></span>')

e = html.escape

# Solo la tarjeta pulsada (o de la que volvemos) lleva nombre de transición.
RJS = """(function(){var r=document.querySelector('.rejilla');if(!r)return;
function off(){r.querySelectorAll('[style*="view-transition-name"]').forEach(function(x){if(!x.dataset.vt)x.dataset.vt=x.style.viewTransitionName;x.style.viewTransitionName='none';});}
function on(a){a.querySelectorAll('[data-vt]').forEach(function(x){x.style.viewTransitionName=x.dataset.vt;});}
off();
r.addEventListener('click',function(e){var a=e.target.closest('.tarjeta');if(a){off();on(a);}});
addEventListener('pagereveal',function(ev){try{var f=navigation.activation.from;if(!ev.viewTransition||!f)return;r.querySelectorAll('.tarjeta').forEach(function(a){if(f.url.indexOf(a.getAttribute('href'))>-1){on(a);ev.viewTransition.finished.finally(off);}});}catch(_){}});
addEventListener('pageshow',function(ev){if(ev.persisted)off();});})();"""


def fecha(iso, lang):
    if not iso:
        return ''
    d = datetime.date.fromisoformat(iso)
    m = MESES[lang][d.month - 1]
    return f'{d.day} de {m} de {d.year}' if lang == 'es' else f'{m} {d.day}, {d.year}'


def descripcion(v, por_defecto):
    """Subtítulo + comienzo de la carta, con sus propias palabras, hasta ~155 caracteres."""
    sub = (v.get('subtitulo') or '').strip()
    ext = re.sub(r'\s+', ' ', (v.get('extracto') or '').replace('…', ' ')).strip()
    if not sub and not ext:
        return por_defecto
    if sub and ext:
        texto = sub + ('' if sub[-1] in '.?!…' else '.') + ' ' + ext
    else:
        texto = sub or ext
    if len(texto) <= 158:
        return texto
    corte = texto[:155].rsplit(' ', 1)[0].rstrip(',;:.')
    return corte + '…'


def mini(ruta, ancho=720):
    """Miniatura ligera para las tarjetas del índice (se genera una vez)."""
    nombre = os.path.basename(ruta)
    destino = os.path.join('assets', 'cartas', 'mini', os.path.splitext(nombre)[0] + '.jpg')
    abs_dest = os.path.join(RAIZ, destino)
    if not os.path.exists(abs_dest):
        try:
            from PIL import Image
            with Image.open(os.path.join(RAIZ, ruta)) as im:
                if im.width <= ancho:
                    return ruta, im.width, im.height
                h = round(im.height * ancho / im.width)
                os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
                im.convert('RGB').resize((ancho, h), Image.LANCZOS).save(
                    abs_dest, format='JPEG', quality=74, optimize=True, progressive=True)
        except Exception as ex:  # sin Pillow o imagen rara: se usa la original
            print('miniatura no generada', ruta, ex)
            return ruta, None, None
    from PIL import Image
    with Image.open(abs_dest) as im:
        return destino, im.width, im.height


def absolutas(htm):
    return re.sub(r'(src|href)="/(?!/)', r'\1="%s/' % SITIO, htm)


def rfc822(iso):
    d = datetime.datetime.fromisoformat(iso).replace(hour=9, tzinfo=datetime.timezone.utc)
    return format_datetime(d)


def escribir(rel, texto):
    with open(os.path.join(RAIZ, rel), 'w', encoding='utf-8') as f:
        f.write(texto)


def feed(lang, lista):
    t = T[lang]
    items = []
    for c in reversed(lista[-30:]):
        v = c[lang]
        url = SITIO + t['base'] + v['slug'] + '/'
        cuerpo = absolutas('\n'.join(bloque_html(b) for b in v['bloques']))
        fecha_rss = f"<pubDate>{rfc822(c['enviada'])}</pubDate>" if c.get('enviada') else ''
        items.append(f"""  <item>
    <title>{e(titulo_num(c, v))}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    {fecha_rss}
    <dc:creator>Antonio de Arcas</dc:creator>
    <description>{e(descripcion(v, ''))}</description>
    <content:encoded><![CDATA[{cuerpo.replace(']]>', ']]]]><![CDATA[>')}]]></content:encoded>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{e(t['feed'])}</title>
  <link>{SITIO}{t['base']}</link>
  <atom:link href="{SITIO}{t['base']}feed.xml" rel="self" type="application/rss+xml"/>
  <description>{e(t['intro_indice'])}</description>
  <language>{lang}</language>
{chr(10).join(items)}
</channel>
</rss>
"""


def sitemap(publicadas):
    urls = []
    for u in FIJAS:
        urls.append(f'  <url><loc>{SITIO}{u}</loc></url>')
    for lang in ('es', 'en'):
        t = T[lang]
        ultima = max((c.get('enviada') or '' for c in publicadas[lang]), default='')
        urls.append(f'  <url><loc>{SITIO}{t["base"]}</loc>' + (f'<lastmod>{ultima}</lastmod>' if ultima else '') + '</url>')
        for c in publicadas[lang]:
            v = c[lang]
            alt = ''
            otro = 'en' if lang == 'es' else 'es'
            if c in publicadas[otro]:
                alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITIO}{T[l]["base"]}{c[l]["slug"]}/"/>' for l in ('es', 'en'))
            mod = f'<lastmod>{c["enviada"]}</lastmod>' if c.get('enviada') else ''
            urls.append(f'  <url><loc>{SITIO}{t["base"]}{v["slug"]}/</loc>{mod}{alt}</url>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + '\n'.join(urls) + '\n</urlset>\n')


def llms(publicadas):
    lineas = ['# Antonio de Arcas', '',
              '> Músico (formado en Berklee), escritor y contemplativo. Escribe Esferas, una carta semanal en español e inglés '
              'sobre mística cristiana, no dualidad y Un Curso de Milagros. / Musician, writer and contemplative. '
              'He writes Esferas, a weekly letter in Spanish and English.', '',
              '## Páginas', '',
              f'- [Inicio]({SITIO}/): suscripción a Esferas',
              f'- [Todo lo que ofrezco]({SITIO}/ofertas/): comunidad Entre el Cielo y la Tierra, acompañamiento y música',
              f'- [Acompañamiento espiritual 1:1]({SITIO}/acompanamiento/)',
              f'- [Música]({SITIO}/musica/)', '']
    for lang, cab in (('es', '## Cartas de Esferas (español)'), ('en', '## Esferas letters (English)')):
        lineas += [cab, '']
        for c in reversed(publicadas[lang]):
            v = c[lang]
            lineas.append(f'- [{titulo_num(c, v)}]({SITIO}{T[lang]["base"]}{v["slug"]}/): {descripcion(v, "")}')
        lineas.append('')
    return '\n'.join(lineas)


def datos_carta(c, v, lang, url, desc, par):
    ld = {
        '@context': 'https://schema.org', '@type': 'BlogPosting',
        'headline': titulo_num(c, v), 'description': desc, 'inLanguage': lang,
        'url': SITIO + url, 'mainEntityOfPage': SITIO + url,
        'author': AUTOR, 'publisher': AUTOR,
        'isPartOf': {'@type': 'Blog', '@id': SITIO + T[lang]['base'] + '#esferas', 'name': 'Esferas',
                     'url': SITIO + T[lang]['base'], 'author': {'@id': AUTOR['@id']}},
        'wordCount': sum(len(b.get('plano', '').split()) for b in v['bloques']),
    }
    if c.get('enviada'):
        ld['datePublished'] = c['enviada']
    if v.get('portada'):
        ld['image'] = SITIO + '/' + v['portada']['ruta']
    if par:
        clave = 'translationOfWork' if lang == 'en' else 'workTranslation'
        ld[clave] = {'@type': 'BlogPosting', 'url': par, 'inLanguage': 'es' if lang == 'en' else 'en'}
    return ld


def pagina_404():
    cuerpo = """<main class="carta-pag error-404">
<article>
  <p class="meta">Error 404</p>
  <h1>Esta página no existe</h1>
  <p class="subtitulo">Quizá cambió de sitio, o quizá nunca estuvo aquí.</p>
  <div class="cuerpo">
<p>Puedes volver al <a href="/">inicio</a> o leer <a href="/cartas/">todas las cartas de Esferas</a>.</p>
<p lang="en"><em>This page doesn't exist. Go back <a href="/">home</a> or read <a href="/en/letters/">all the Esferas letters</a>.</em></p>
  </div>
</article>
</main>"""
    h = pagina('es', 'Página no encontrada · Antonio de Arcas', 'Esta página no existe.', cuerpo, '', '/en/letters/',
               'pag-carta', canon='/404.html', par=False)
    h = '\n'.join(l for l in h.split('\n') if 'rel="canonical"' not in l and 'hreflang="' not in l.split('<a ')[0]
                  and 'og:url' not in l)
    return h.replace('<meta name="viewport"', '<meta name="robots" content="noindex">\n<meta name="viewport"', 1)


def pagina_sobre(lang):
    """Página Sobre mí (texto en datos/sobre.json). Define a Antonio para buscadores e IA."""
    with open(os.path.join(RAIZ, 'datos', 'sobre.json'), encoding='utf-8') as f:
        d = json.load(f)
    v, otro = d[lang], d['en' if lang == 'es' else 'es']
    foto = 'assets/foto.jpg'
    c = v['contacto']
    cuerpo = f"""<main class="carta-pag sobre">
<article>
  <h1>{e(v['h1'])}</h1>
  <p class="subtitulo">{e(v['sub'])}</p>
  <figure class="lamina">{img(foto, 1400, 922, v['alt'], lazy=False)}</figure>
  <div class="cuerpo">
<div class="intro">{v['intro']}</div>
{chr(10).join(v['cuerpo'])}
  </div>
  <aside class="contacto">
    <h2>{e(c['t'])}</h2>
{('    <p>' + e(c['p']) + '</p>' + chr(10)) if c.get('p') else ''}    <p class="botones"><a class="pastilla" href="{e(c['wa'])}" target="_blank" rel="noopener">{e(c['wa_t'])}</a></p>
    <p class="o">{e(c['o_t'])}</p>
    <p class="botones"><a class="pastilla clara" href="{e(c['mail'])}">{e(c['mail_t'])}</a></p>
  </aside>
</article>
{alta(lang)}
</main>"""
    persona = dict(AUTOR, description=v['desc'], jobTitle=v['sub'],
                   image=SITIO + '/' + foto,
                   alumniOf={'@type': 'CollegeOrUniversity', 'name': 'Berklee College of Music'},
                   knowsAbout=['Christian mysticism', 'Advaita Vedanta', 'A Course in Miracles', 'Taoism', 'Zen', 'Music'])
    ld = {'@context': 'https://schema.org', '@type': 'ProfilePage', 'url': SITIO + v['url'], 'inLanguage': lang,
          'mainEntity': persona}
    h = pagina(lang, v['titulo'], v['desc'], cuerpo, v['url'], otro['url'], 'pag-carta pag-sobre', foto, v['url'],
               par=True, tipo='profile', ld=ld)
    os.makedirs(os.path.join(RAIZ, v['url'].strip('/')), exist_ok=True)
    escribir(os.path.join(v['url'].strip('/'), 'index.html'), h)


def visible(c, hoy, todas):
    if todas:
        return c.get('estado') != 'descartada'
    if c.get('estado') == 'publicada':
        return True
    return c.get('estado') == 'aprobada' and c.get('publicar') and c['publicar'] <= hoy


def pagina(lang, titulo, desc, cuerpo, actual, otra_url, clase='', imagen=None, canon='', par=True, tipo='website', publicada=None, ld=None):
    t = T[lang]
    nav = ' '.join('<a href="%s"%s>%s</a>' % (u, ' aria-current="page"' if u == actual else '', n) for u, n in t['nav'])
    es_url, en_url = (canon, otra_url) if lang == 'es' else (otra_url, canon)
    idiomas = ('<span class="idiomas"><a href="%s" lang="es" hreflang="es"%s>ES</a><span aria-hidden="true">·</span>'
               '<a href="%s" lang="en" hreflang="en"%s>EN</a></span>') % (
        es_url, ' aria-current="true"' if lang == 'es' else '', en_url, ' aria-current="true"' if lang == 'en' else '')
    og = '<meta property="og:image" content="https://antoniodearcas.com/assets/compartir.jpg">\n'
    if imagen:
        og = '<meta property="og:image" content="https://antoniodearcas.com/%s">\n' % imagen
    extra = (f'<meta property="og:type" content="{tipo}">\n<meta property="og:url" content="{SITIO}{canon}">\n'
             f'<meta property="og:site_name" content="Antonio de Arcas">\n'
             f'<meta property="og:locale" content="{"es_ES" if lang == "es" else "en_US"}">\n'
             '<meta name="twitter:card" content="summary_large_image">\n')
    if publicada:
        extra += f'<meta property="article:published_time" content="{publicada}">\n<meta name="author" content="Antonio de Arcas">\n'
    if ld:
        extra += '<script type="application/ld+json">%s</script>\n' % json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')
    # hreflang: cada versión se nombra a sí misma, a su traducción y la española como x-default
    alternos = f'<link rel="alternate" hreflang="{lang}" href="{SITIO}{canon}">\n'
    if par:
        alternos += f'<link rel="alternate" hreflang="{"en" if lang == "es" else "es"}" href="{SITIO}{otra_url}">\n'
        alternos += f'<link rel="alternate" hreflang="x-default" href="{SITIO}{es_url}">\n'
    elif lang == 'es':
        alternos += f'<link rel="alternate" hreflang="x-default" href="{SITIO}{canon}">\n'
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(desc)}">
{og}{extra}<link rel="canonical" href="{SITIO}{canon}">
{alternos}<link rel="alternate" type="application/rss+xml" title="{e(t['feed'])}" href="{t['base']}feed.xml">
<link rel="icon" href="/assets/favicon.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="https://use.typekit.net/jjg8lnx.css">
<link rel="stylesheet" href="/assets/estilo.css?v=24">
<link rel="stylesheet" href="/assets/cartas.css?v={V}">
</head>
<body class="cartas {clase}">
<header><a href="/" aria-label="{t['inicio']}"><img class="logo" src="/assets/logo.png" alt=""><img class="marca" src="/assets/marca.png" alt="Antonio de Arcas"></a><button class="abrir" type="button" aria-label="{t['menu_a']}" data-cerrar="{t['menu_c']}" aria-expanded="false" aria-controls="menu"><span></span><span></span></button><nav class="menu" id="menu" aria-label="{t['secciones']}">{nav}{idiomas}</nav></header>
{cuerpo}
<footer class="pie"><span class="texto">© {datetime.date.today().year} Antonio de Arcas<span>·</span><a href="/privacidad/">{t['privacidad']}</a></span>{REDES}</footer>
<script src="/assets/cartas.js?v={V}" defer></script>
</body>
</html>
'''


def img(ruta, w, h, alt='', vt=None, lazy=True, sizes=''):
    estilo = f' style="view-transition-name:{vt}"' if vt else ''
    carga = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return f'<img src="/{ruta}" width="{w}" height="{h}" alt="{e(alt)}"{carga}{estilo}>'


def bloque_html(b):
    if b['t'] == 'img':
        i = img(b['ruta'], b['w'], b['h'])
        if b.get('href'):
            i = f'<a href="{e(b["href"])}" target="_blank" rel="noopener">{i}</a>'
        return f'<figure>{i}</figure>'
    if b['t'] == 'boton':
        return f'<p class="boton-carta"><a class="pastilla" href="{e(b["href"])}" target="_blank" rel="noopener">{e(b["texto"])}</a></p>'
    if b['t'] == 'intro':
        return f'<div class="intro">{b["html"]}</div>'
    if b['t'] == 'firma':
        return f'<div class="firma">{b["html"]}</div>'
    return b['html']


def alta(lang):
    t = T[lang]
    return f'''<aside class="alta-carta">
  <h2>{t['alta_t']}</h2>
  <p>{t['alta_p']}</p>
  <form class="form alta" novalidate data-hook="{HOOK}" data-idioma="{t['idioma']}" data-m-email="{e(t['m_email'])}" data-m-priv="{e(t['m_priv'])}" data-m-env="{e(t['m_env'])}" data-m-ok="{e(t['m_ok'])}" data-m-err="{e(t['m_err'])}">
    <input type="email" name="Email" placeholder="{t['email']}" autocomplete="email" required aria-label="{t['email']}">
    <label class="check"><input type="checkbox" name="Newsletter" required> <span>{t['acepto']}</span></label>
    <div class="trampa" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></div>
    <button class="boton" type="submit">{t['boton']}</button>
    <p class="mensaje" role="status" aria-live="polite"></p>
  </form>
</aside>'''


def titulo_num(c, v):
    return '%d. %s' % (c['num'], v['titulo'])


def tarjeta(c, v, lang, prioridad=False):
    t = T[lang]
    p = v.get('portada')
    if p:
        r, w, h = mini(p['ruta'])
        w, h = (w, h) if w else (p['w'], p['h'])
    figura = img(r, w, h, v['titulo'], vt='c%d' % c['num'], lazy=not prioridad) if p else \
        '<span class="sin-imagen" style="view-transition-name:c%d"><img src="/assets/esferas.png" alt=""></span>' % c['num']
    sub = v.get('subtitulo') or v.get('extracto') or ''
    meta = f'<time class="meta" datetime="{c["enviada"]}">{fecha(c["enviada"], lang)}</time>' if c.get('enviada') else ''
    return f'''<a class="tarjeta" href="{t['base']}{v['slug']}/">
  <span class="marco">{figura}</span>
  {meta}
  <h2 style="view-transition-name:t{c['num']}">{e(titulo_num(c, v))}</h2>
  <span class="extracto">{e(sub)}</span>
</a>'''


def construir(hoy, todas):
    cartas = sorted(cargar_todas(), key=lambda c: c['num'])
    publicadas = {}
    for lang in ('es', 'en'):
        t = T[lang]
        base_dir = os.path.join(RAIZ, t['base'].strip('/'))
        if os.path.isdir(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)
        lista = [c for c in cartas if lang in c and visible(c, hoy, todas)]
        otro = 'en' if lang == 'es' else 'es'
        # páginas de carta
        for i, c in enumerate(lista):
            v = c[lang]
            url = t['base'] + v['slug'] + '/'
            par = c.get(otro) if visible(c, hoy, todas) else None
            otra_url = (T[otro]['base'] + par['slug'] + '/') if par else T[otro]['base']
            ant = lista[i - 1] if i > 0 else None
            sig = lista[i + 1] if i + 1 < len(lista) else None
            p = v.get('portada')
            bloques = list(v['bloques'])
            if p:  # la portada se muestra arriba; se quita del cuerpo
                for j, b in enumerate(bloques):
                    if b['t'] == 'img' and b['ruta'] == p['ruta']:
                        bloques.pop(j)
                        break
            meta = f'<p class="meta"><time datetime="{c["enviada"]}">{fecha(c["enviada"], lang)}</time></p>' if c.get('enviada') else ''
            portada = f'<figure class="lamina">{img(p["ruta"], p["w"], p["h"], v["titulo"], vt="c%d" % c["num"], lazy=False)}</figure>' if p else ''
            sub = f'<p class="subtitulo">{e(v["subtitulo"])}</p>' if v.get('subtitulo') else ''

            def vecina(x, rot, cls):
                if not x:
                    return '<span></span>'
                vv = x[lang]
                return f'<a class="{cls}" href="{t["base"]}{vv["slug"]}/"><span class="rot">{rot}</span><span class="tit">{e(titulo_num(x, vv))}</span></a>'
            cuerpo = f'''<main class="carta-pag">
<article>
  <a class="volver" href="{t['base']}">← {t['volver']}</a>
  {meta}
  <h1 style="view-transition-name:t{c['num']}">{e(titulo_num(c, v))}</h1>
  {sub}
  {portada}
  <div class="cuerpo">
{chr(10).join(bloque_html(b) for b in bloques)}
  </div>
</article>
{alta(lang)}
<nav class="vecinas" aria-label="{t['nombre']}">{vecina(ant, '← ' + t['anterior'], 'ant')}{vecina(sig, t['siguiente'] + ' →', 'sig')}</nav>
</main>'''
            desc = descripcion(v, t['desc_indice'])
            ld = datos_carta(c, v, lang, url, desc, (SITIO + otra_url) if par else None)
            d = os.path.join(base_dir, v['slug'])
            os.makedirs(d)
            with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(pagina(lang, f"{titulo_num(c, v)} · {t['serie']}", desc, cuerpo, t['base'], otra_url,
                               'pag-carta', p['ruta'] if p else None, url, par=bool(par), tipo='article',
                               publicada=c.get('enviada'), ld=ld))
        # índice
        tarjetas = '\n'.join(tarjeta(c, c[lang], lang, i < 4) for i, c in enumerate(reversed(lista)))
        cuerpo = f'''<main class="indice-cartas">
<section class="cabecera">
  <img class="esferas-logo" src="/assets/esferas.png" alt="Esferas">
  <p>{t['intro_indice']}</p>
  <a class="pastilla clara" href="#alta">{t['recibir']}</a>
</section>
<div class="rejilla">
{tarjetas}
</div>
<script>{RJS}</script>
<div id="alta">{alta(lang)}</div>
</main>'''
        with open(os.path.join(base_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(pagina(lang, f"{t['titulo_indice']} · Esferas · Antonio de Arcas", t['desc_indice'], cuerpo,
                           t['base'], T[otro]['base'], 'pag-indice', None, t['base'],
                           ld={'@context': 'https://schema.org', '@type': 'Blog', '@id': SITIO + t['base'] + '#esferas',
                               'name': 'Esferas', 'description': t['intro_indice'], 'url': SITIO + t['base'],
                               'inLanguage': lang, 'author': AUTOR}))
        escribir(os.path.join(t['base'].strip('/'), 'feed.xml'), feed(lang, lista))
        publicadas[lang] = lista
        print(lang, len(lista), 'cartas')
    escribir('404.html', pagina_404())
    pagina_sobre('es')
    pagina_sobre('en')
    escribir('sitemap.xml', sitemap(publicadas))
    escribir('llms.txt', llms(publicadas))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--hoy', default=datetime.date.today().isoformat())
    ap.add_argument('--todas', action='store_true')
    a = ap.parse_args()
    construir(a.hoy, a.todas)
