""" HTTP interface and processing

Various HTTP routes the external world uses to communicate with the application.
"""

import bottle as bt
import cgi
import logging
import re
from pathlib import Path
from metrics import Time
from bin import root, config, models
from bin.highlight import highlight, parse_extension, parse_language, validate_extension, languages


logger = logging.getLogger(__name__)
BOTUARE = re.compile(r'|'.join([
    re.escape('Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)'),
    re.escape('facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'),
]))


@bt.route('/health', method='GET')
def healthcheck():
    """ Get a dummy string 'alive' to ensure the server is responding """
    return "alive"


@bt.route('/', method='GET')
def get_new_form():
    """
    Get the browser-friendly html form to easily post a new snippet

    :param lang: (query) optional lang that is selected in the lang selection instead of the configured default
    :param parentid: (query) optional 'parent' snippet to duplicate the code from

    :raises HTTPError: code 404 when the 'parent' snippet is not found
    """
    parentid = bt.request.query.parentid
    lang = bt.request.query.lang or config.DEFAULT_LANGUAGE

    try:
        code = models.Snippet.get_by_id(parentid).code if parentid else ""
    except KeyError:
        raise bt.HTTPError(404, "Parent snippet not found")

    return bt.template(
        'newform.html',
        languages=languages,
        default_language=lang,
        code=code,
        parentid=parentid,
    )


@bt.route('/assets/<filepath:path>')
def assets(filepath):
    """
    Get a static css/js/media file that is stored in the filesystem.

    This route exists for developers of bin who wish to run the service
    with minimum system requirements. In production, we suggest you use
    a web server to deliver the static content.
    """
    return bt.static_file(filepath, root=root.joinpath('assets'))


@bt.route('/new', method='POST')
def post_new():
    """
    Post a new snippet and redirect the user to the generated unique URL
    for the snippet.

    :param code: (form) required snippet text, can alternativaly be sent as a Multi-Part utf-8 file
    :param lang: (form) optionnal language
    :param maxusage: (form) optionnal maximum download of the snippet before it is deleted
    :param lifetime: (form) optionnal time (defined in seconds) the snippet is keep in the database before it is deleted
    :param parentid: (form) optionnal snippet id this new snippet is a duplicate of

    :raises HTTPError: code 411 when the ``Content-Length`` http header is missing
    :raises HTTPError: code 413 when the http request is too large (mostly because the snippet is too long)
    :raises HTTPError: code 400 with a sensible status when the form processing fails
    """
    content_length = bt.request.get_header('Content-Length')
    if content_length is None:
        raise bt.HTTPError(411, "Content-Length required")
    if int(content_length) > config.MAXSIZE:
        raise bt.HTTPError(413, f"Payload too large, we accept maximum {config.MAXSIZE}")

    files = bt.request.files
    forms = bt.request.forms

    code = None
    ext = config.DEFAULT_LANGUAGE
    maxusage = config.DEFAULT_MAXUSAGE
    lifetime = config.DEFAULT_LIFETIME
    parentid = ''

    try:
        if files:
            part = next(files.values())
            charset = cgi.parse_header(part.content_type)[1].get('charset', 'utf-8')
            code = part.file.read(config.MAXSIZE).decode(charset)
            filename = part.filename
            if filename:
                ext = validate_extension(Path(filename.casefold()).suffix.lstrip('.')) or ext
        if forms:
            # WSGI forces latin-1 decoding, this is wrong, we recode it in utf-8
            code = forms.get('code', '').encode('latin-1').decode() or code
            lang = forms.get('lang')
            if lang:
                ext = parse_language(lang.casefold()) or ext
            maxusage = int(forms.get('maxusage') or maxusage)
            lifetime = Time(forms.get('lifetime') or lifetime)
            parentid = forms.get('parentid', '')

        if not code:
            raise ValueError("Code is missing")
        if maxusage < 0:
            raise ValueError("Maximum usage must be positive")
        if lifetime < 0:
            raise ValueError("Lifetime must be positive")
        if parentid:
            try:
                models.Snippet.get_by_id(parentid)
            except KeyError:
                raise ValueError("Parent does not exist")
    except ValueError as exc:
        raise bt.HTTPError(400, str(exc))

    snippet = models.Snippet.create(code, maxusage, lifetime, parentid)
    logger.info("New %s snippet of %s chars: %s", lang, len(code), snippet.id)
    bt.redirect(f'/{snippet.id}.{ext}')


@bt.route('/<snippetid>', method='GET')
@bt.route('/<snippetid>.<ext>', method='GET')
def get_html(snippetid, ext=None):
    """
    Get a snippet in a beautiful html page

    :param snippetid: (path) required snippet id
    :param ext: (path) optional language file extension, used to determine the highlight backend

    :raises HTTPError: code 404 when the snippet is not found
    """
    if BOTUARE.match(bt.request.headers.get('User-Agent', '')):
        return bt.template('blank.html')

    try:
        snippet = models.Snippet.get_by_id(snippetid)
    except KeyError:
        raise bt.HTTPError(404, "Snippet not found")
    lang = parse_extension(ext) or config.DEFAULT_LANGUAGE
    codehl = highlight(snippet.code, lang)
    return bt.template(
        'highlight.html',
        codehl=codehl,
        lang=lang,
        ext=ext,
        snippetid=snippetid,
        parentid=snippet.parentid,
    )


@bt.route('/raw/<snippetid>', method='GET')
@bt.route('/raw/<snippetid>.<ext>', method='GET')
def get_raw(snippetid, ext=None):
    """
    Get a snippet in plain text without code hightlight

    :param snippetid: (path) required snippet id
    :param ext: (path) ignored parameter
    """
    if BOTUARE.match(bt.request.headers.get('User-Agent', '')):
        return bt.template('blank.html')

    try:
        snippet = models.Snippet.get_by_id(snippetid)
    except KeyError:
        raise bt.HTTPError(404, "Snippet not found")

    bt.response.headers['Content-Type'] = 'text/plain'
    return snippet.code

@bt.route('/report', method='POST')
def report():
    """
    Report a problematic snippet to the system administrator.

    :param snippetid: (form) the reported snippet
    :param name: (form) the name of the user reporting the problem

    :raises HTTPError: code 400 when any of the snippetid or the name is missing
    :raises HTTPError: code 404 when the reported snippet is not found
    """
    name = bt.request.forms.get("name", "").encode('latin-1').decode().strip()
    snippetid = bt.request.forms.get("snippetid")
    if not name:
        raise bt.HTTPError(400, "Missing name")
    if not snippetid:
        raise bt.HTTPError(400, "Missing snippetid")

    try:
        models.Snippet.get_by_id(snippetid)
    except KeyError:
        raise bt.HTTPError(404, "Snippet not found")
    logger.warning("The snippet %s got reported by %s", snippetid, name)

    return bt.HTTPResponse("The snippet have been reported.")
