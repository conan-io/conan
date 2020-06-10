# coding=utf-8

import functools
from conans.errors import ConanException

import logging
log = logging.getLogger(__name__)


class FormatterFormats(object):
    _registry = {}

    @classmethod
    def register(cls, format):
        def real_decorator(formatter_class):
            log.debug("Formats::register: {})".format(formatter_class))
            cls._registry[format] = formatter_class
            return formatter_class
        return real_decorator

    @classmethod
    @functools.lru_cache()
    def get(cls, format, *args, **kwargs):
        _class = cls._registry.get(format, None)
        if not _class:
            raise ConanException("Formatter for format '{}' not found".format(format))
        return _class(*args, **kwargs)
