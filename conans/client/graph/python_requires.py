from collections import namedtuple

from conans.client.loader import parse_conanfile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement


PythonRequire = namedtuple("PythonRequire", "conan_ref module")


class ConanPythonRequire(object):
    def __init__(self, proxy, range_resolver):
        self._cached_requires = {}  # {conan_ref: PythonRequire}
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._requires = []

    @property
    def requires(self):
        result = self._requires
        self._requires = []
        return result

    def __call__(self, require):
        try:
            python_require = self._cached_requires[require]
        except KeyError:
            r = ConanFileReference.loads(require)
            requirement = Requirement(r)
            self._range_resolver.resolve(requirement, "python_require", update=False,
                                         remote_name=None)
            r = requirement.conan_reference
            result = self._proxy.get_recipe(r, False, False, remote_name=None,
                                            recorder=ActionRecorder())
            path, _, _, reference = result
            module, _ = parse_conanfile(path)
            python_require = PythonRequire(reference, module)
            self._cached_requires[require] = python_require
        self._requires.append(python_require)
        return python_require.module
