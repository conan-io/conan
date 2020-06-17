# coding=utf-8

from conans.errors import ConanException


class BaseFormatter(object):
    @classmethod
    def out(cls, out_format, *args, **kwargs):
        try:
            format_func = getattr(cls, out_format)
        except Exception:
            raise ConanException("Unknown format '{}' in formatter.".format(out_format))
        return format_func(*args, **kwargs)
