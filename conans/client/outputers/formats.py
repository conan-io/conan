# coding=utf-8

import functools
from conans.errors import ConanException

import logging
log = logging.getLogger(__name__)


class OutputerFormats(object):
    _registry = {}

    @classmethod
    def register(cls, format):
        def real_decorator(outputer_class):
            log.debug("Formats::register: {})".format(outputer_class))
            cls._registry[format] = outputer_class
            return outputer_class
        return real_decorator

    @classmethod
    @functools.lru_cache()
    def get(cls, format, *args, **kwargs):
        _class = cls._registry.get(format, None)
        if not _class:
            raise ConanException("Outputer for format '{}' not found".format(format))
        return _class(*args, **kwargs)
