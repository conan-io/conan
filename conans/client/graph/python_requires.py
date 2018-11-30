from collections import namedtuple

from conans.client.loader import parse_conanfile, parse_module
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement
from contextlib import contextmanager


PythonRequire = namedtuple("PythonRequire", "conan_ref module")


class ConanPythonRequire(object):
    def __init__(self, proxy, range_resolver):
        self._cached_requires = {}  # {conan_ref: PythonRequire}
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._requires = None

    @contextmanager
    def capture_requires(self):
        old_requires = self._requires
        self._requires = []
        yield self._requires
        self._requires = old_requires

    def _look_for_require(self, require):
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
            with self.capture() as py_requires:
                module, filename = parse_conanfile(path)
                module.python_requires = py_requires

            # Check for alias
            conanfile = parse_module(module, filename)
            if getattr(conanfile, "alias", None):
                # Will register also the aliased
                python_require = self._look_for_require(conanfile.alias)
            else:
                python_require = PythonRequire(reference, module)
            self._cached_requires[require] = python_require

        return python_require

    def __call__(self, require):
        python_req = self._look_for_require(require)
        self._requires.append(python_req)
        return python_req.module
