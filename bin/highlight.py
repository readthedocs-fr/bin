""" HTML highlighted code export and language tools """


import pygments
from pygments.lexers import get_all_lexers, get_lexer_by_name
from pygments.formatters.html import HtmlFormatter

languages = [
    # (ext, lang)
    ('c', 'c'),
    ('cpp', 'cpp'),
    ('cs', 'csharp'),
    ('css', 'css'),
    ('dart', 'dart'),
    ('diff', 'diff'),
    ('erl', 'erlang'),
    ('ex', 'elixir'),
    ('go', 'go'),
    ('h', 'objectivec'),
    ('hs', 'haskell'),
    ('html', 'html'),
    ('ini', 'ini'),
    ('java', 'java'),
    ('js', 'javascript'),
    ('json', 'json'),
    ('julia', 'jl'),
    ('kt', 'kotlin'),
    ('less', 'less'),
    ('lisp', 'lisp'),
    ('lua', 'lua'),
    ('md', 'markdown'),
    ('php', 'php'),
    ('pl', 'perl'),
    ('py', 'python'),
    ('rb', 'ruby'),
    ('rs', 'rust'),
    ('sass', 'sass'),
    ('scala', 'scala'),
    ('scss', 'scss'),
    ('sh', 'bash'),
    ('sql', 'sql'),
    ('swift', 'swift'),
    ('toml', 'toml'),
    ('ts', 'typescript'),
    ('txt', 'text'),
    ('xml', 'xml'),
    ('yml', 'yaml'),
]
exttolang = {ext: lang for ext, lang in languages}
langtoext = {lang: ext for ext, lang in languages}

for n, aliases, filenames, _ in get_all_lexers():
    # some lexers doesn't have aliases or doesn't have filenames (such as JsonBareObjectLexer),
    # theses are ignored
    if len(aliases) == 0 or len(filenames) == 0:
        continue

    # even if the first alias is not always the same as the name,
    # it is usually better than the other aliases (which can be equal to the name)
    name = aliases[0]
    ext = filenames[0][2:]  # remove the *. from the filename
    if name not in langtoext:
        langtoext[name] = ext 
    if ext not in exttolang:
        exttolang[ext] = name

def validate_extension(ext):
    """ Validate a language extension, returns it's extension or `None` """
    if ext in exttolang:
        return ext
    return langtoext.get(ext)  # ext is maybe a language name

def parse_language(lang):
    """ Validate a language name, returns it's extension or `None` """
    if lang in langtoext:
        return langtoext.get(lang)  
    if lang in exttolang:
        return lang  # this is already an extension

def parse_extension(ext):
    """ From a language extension, get a language """
    if ext in exttolang:
        return exttolang.get(ext)
    if ext in langtoext:
        return ext  # this is already a lang

class _TableHtmlFormatter(HtmlFormatter):
    """
    Extension to the default pygment HtmlFormatter to control the html
    skeleton output, class names and line numbering.
    """
    def __init__(self, **options):
        super().__init__(**options)
        if options.get('linenos', False) == 'bin-table':
            self.linenos = 3

    def wrap(self, source, outfile):
        if self.linenos == 3:
            source = self._wrap_table(source)
        yield from source

    def _wrap_table(self, inner):
        yield 0, '<table class="highlight"><tbody>'
        for i, (t, l) in enumerate([*inner, (1, '')]):
            yield t, f'<tr><td class="line-number" id=L{i + 1} value={i + 1}></td><td class="line-content">{l}</td></tr>\n'
        yield 0, '</tbody></table>'


_html_formatter = _TableHtmlFormatter(linenos='bin-table', style='monokai')


def highlight(code, language):
    """ Pretty html export of ``code`` using syntax highlighting """
    lexer = get_lexer_by_name(language, startinline=True)
    return pygments.highlight(code, lexer, _html_formatter)
