# coding=utf-8

from conans.errors import ConanException


class BaseOutputer(object):

    def out(self, f, *args, **kwargs):
        func_call = getattr(self, f, None)
        if not func_call:
            raise ConanException("Unknown method '{}' in outputer".format(f))

        return func_call(*args, **kwargs)

    def search(self, *args, **kwargs):
        raise NotImplementedError

