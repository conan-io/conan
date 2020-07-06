import argparse

from conans.cli.cli import SmartFormatter
from conans.errors import ConanException


class ConanCommand(object):
    def __init__(self, method, group=None, **kwargs):
        self._formatters = {}
        for kind, action in kwargs.items():
            if callable(action):
                self._formatters[kind] = action
        self._group = group or "Misc commands"
        self._name = method.__name__.replace("_", "-")
        self._method = method
        if method.__doc__:
            self._doc = method.__doc__
        else:
            raise ConanException("No documentation string defined for command: '{}'. Conan "
                                 "commands should provide a documentation string explaining "
                                 "its use briefly.".format(self._name))
        self._parser = argparse.ArgumentParser(description=self._doc,
                                               prog="conan {}".format(self._name),
                                               formatter_class=SmartFormatter)

    def run(self, *args, **kwargs):
        conan_api = kwargs["conan_api"]
        info, formatter = self._method(*args, **kwargs)
        if info:
            self._formatters[formatter](info, conan_api.out)

    @property
    def group(self):
        return self._group

    @property
    def name(self):
        return self._name

    @property
    def method(self):
        return self._method

    @property
    def doc(self):
        return self._doc

    @property
    def parser(self):
        return self._parser


def conan_command(**kwargs):
    def decorator(f):
        cmd = ConanCommand(f, **kwargs)
        return cmd

    return decorator
