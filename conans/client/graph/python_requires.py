from collections import namedtuple
from contextlib import contextmanager

from conans.client.loader import parse_conanfile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement
from conans.errors import ConanException

PythonRequire = namedtuple("PythonRequire", "conan_ref module conanfile")


class ConanPythonRequire(object):
    def __init__(self, proxy, range_resolver):
        self._cached_requires = {}  # {conan_ref: PythonRequire}
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._requires = None
        self.valid = True

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
            module, conanfile = parse_conanfile(conanfile_path=path, python_requires=self)

            # Check for alias
            if getattr(conanfile, "alias", None):
                # Will register also the aliased
                python_require = self._look_for_require(conanfile.alias)
            else:
                python_require = PythonRequire(reference, module, conanfile)
            self._cached_requires[require] = python_require

        return python_require

    def __call__(self, require):
        if not self.valid:
            raise ConanException("Invalid use of python_requires(%s)" % require)
        python_req = self._look_for_require(require)
        self._requires.append(python_req)
        return python_req.module
