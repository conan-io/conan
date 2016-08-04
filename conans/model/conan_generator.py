from conans.errors import ConanException
from abc import ABCMeta, abstractproperty


class Generator(object):
    __metaclass__ = ABCMeta

    def __init__(self, conanfile):
        self.conanfile = conanfile
        self._deps_build_info = conanfile.deps_cpp_info
        self._build_info = conanfile.cpp_info
        self._deps_env_info = conanfile.deps_env_info
        self._env_info = conanfile.env_info

    @property
    def deps_build_info(self):
        return self._deps_build_info

    @property
    def build_info(self):
        return self._build_info

    @property
    def deps_env_info(self):
        return self._deps_env_info

    @property
    def env_info(self):
        return self._env_info

    @abstractproperty
    def content(self):
        raise NotImplementedError()

    @abstractproperty
    def filename(self):
        raise NotImplementedError()


class GeneratorManager(object):
    def __init__(self):
        self._known_generators = {}

    def add(self, name, generator_class):
        if name in self._known_generators:
            raise ConanException("")
        elif not issubclass(generator_class, Generator):
            raise ConanException("")
        else:
            self._known_generators[name] = generator_class

    def remove(self, name):
        if name in self._known_generators:
            del self._known_generators[name]

    @property
    def available(self):
        return list(self._known_generators.keys())

    def __contains__(self, key):
        return key in self._known_generators

    def __getitem__(self, key):
        return self._known_generators[key]
