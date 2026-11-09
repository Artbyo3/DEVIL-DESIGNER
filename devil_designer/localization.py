import json
from functools import lru_cache
from pathlib import Path

try:
    import bpy
except ImportError:
    bpy = None

LOCALE_FOLDER = Path(__file__).parent / 'locales'


@lru_cache(maxsize=None)
def catalog(name):
    try:
        data = json.loads((LOCALE_FOLDER / (name + '.json')).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: value for key, value in data.items() if isinstance(key, str) and isinstance(value, str) and value}


def active_locale():
    try:
        if not bpy.context.preferences.view.use_translate_interface:
            return ''
        return str(bpy.app.translations.locale or '')
    except (AttributeError, TypeError):
        return ''


def locale_files(locale):
    if not locale or locale == 'en' or locale.startswith('en_'):
        return ()
    base = locale.split('@')[0].split('_')[0]
    return tuple(dict.fromkeys((locale, base)))


def translate(text, locale=None):
    if not isinstance(text, str) or not text:
        return text
    for name in locale_files(active_locale() if locale is None else locale):
        value = catalog(name).get(text)
        if value:
            return value
    return text
