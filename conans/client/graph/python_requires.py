import imp
import sys
import os

from conans.model.ref import ConanFileReference
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.requires import Requirement


class ConanPythonRequire(object):
    def __init__(self, proxy, range_resolver):
        self._modules = {}
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._references = []

    @property
    def references(self):
        result = self._references
        self._references = []
        return result

    def __call__(self, require):
        try:
            m, reference = self._modules[require]
            self._references.append(reference)
            return m
        except KeyError:
            r = ConanFileReference.loads(require)
            requirement = Requirement(r)
            self._range_resolver.resolve(requirement, "python_require", update=False,
                                         remote_name=None)
            r = requirement.conan_reference
            result = self._proxy.get_recipe(r, False, False, remote_name=None,
                                            recorder=ActionRecorder())
            path, _, _, reference = result
            self._references.append(reference)
            try:
                sys.path.append(os.path.dirname(path))
                module = imp.load_source("python_require", path)
            finally:
                sys.path.pop()
            self._modules[require] = module, reference
        return module
