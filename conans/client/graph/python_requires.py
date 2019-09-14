from collections import namedtuple
from contextlib import contextmanager

from conans.client.loader import parse_conanfile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement
from conans.errors import ConanException, NotFoundException

PythonRequire = namedtuple("PythonRequire", ["ref", "module", "conanfile",
                                             "exports_folder", "exports_sources_folder"])


class PyRequireLoader(object):
    def __init__(self, proxy, range_resolver):
        self._proxy = proxy
        self._range_resolver = range_resolver

    def enable_remotes(self, check_updates=False, update=False, remotes=None):
        self._check_updates = check_updates
        self._update = update
        self._remotes = remotes

    @contextmanager
    def capture_requires(self):
        yield []

    def load_py_requires(self, conanfile):
        if not hasattr(conanfile, "py_requires"):
            return
        py_requires = conanfile.py_requires
        if isinstance(py_requires, str):
            py_requires = [py_requires, ]

        py_requires = self._resolve_py_requires(py_requires)
        if hasattr(conanfile, "py_requires_extend"):
            py_requires_extend = conanfile.py_requires_extend
            if isinstance(py_requires_extend, str):
                py_requires_extend = [py_requires_extend, ]
            for p in py_requires_extend:
                pkg, class_name = p.split(".")
                pkg_module = getattr(py_requires[pkg].module, class_name)
                conanfile.__bases__ = (pkg_module,) + conanfile.__bases__
        conanfile.py_requires = py_requires
        return py_requires

    def _resolve_py_requires(self, py_requires):
        result = {}
        for py_require in py_requires:
            ref = ConanFileReference.loads(py_require)
            requirement = Requirement(ref)
            self._range_resolver.resolve(requirement, "python_require", update=self._update,
                                         remotes=self._remotes)
            ref = requirement.ref
            recipe = self._proxy.get_recipe(ref, self._check_updates, self._update,
                                            remotes=self._remotes,
                                            recorder=ActionRecorder())
            path, _, _, new_ref = recipe
            module, conanfile = parse_conanfile(conanfile_path=path, python_requires=self)
            if getattr(conanfile, "alias", None):
                # Will register also the aliased
                aliased = self._resolve_py_requires([conanfile.alias])
                result.update(aliased)
            else:
                py_req = PythonRequire(new_ref, module, conanfile, None, None)
                result[ref.name] = py_req
                child = self.load_py_requires(conanfile)
                # FIXME: Deal with conflicts here instead of updating
                if child is not None:
                    result.update(child)
        return result


class ConanPythonRequire(object):
    def __init__(self, proxy, range_resolver):
        self._cached_requires = {}  # {reference: PythonRequire}
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._requires = None
        self.valid = True
        self._check_updates = False
        self._update = False
        self._remote_name = None
        self.locked_versions = None

    def enable_remotes(self, check_updates=False, update=False, remotes=None):
        self._check_updates = check_updates
        self._update = update
        self._remotes = remotes

    @contextmanager
    def capture_requires(self):
        old_requires = self._requires
        self._requires = []
        yield self._requires
        self._requires = old_requires

    def _look_for_require(self, reference):
        ref = ConanFileReference.loads(reference)
        ref = self.locked_versions[ref.name] if self.locked_versions is not None else ref
        try:
            python_require = self._cached_requires[ref]
        except KeyError:
            requirement = Requirement(ref)
            self._range_resolver.resolve(requirement, "python_require", update=self._update,
                                         remotes=self._remotes)
            ref = requirement.ref
            result = self._proxy.get_recipe(ref, self._check_updates, self._update,
                                            remotes=self._remotes,
                                            recorder=ActionRecorder())
            path, _, _, new_ref = result
            module, conanfile = parse_conanfile(conanfile_path=path, python_requires=self)

            # Check for alias
            if getattr(conanfile, "alias", None):
                # Will register also the aliased
                python_require = self._look_for_require(conanfile.alias)
            else:
                package_layout = self._proxy._cache.package_layout(new_ref, conanfile.short_paths)
                exports_sources_folder = package_layout.export_sources()
                exports_folder = package_layout.export()
                python_require = PythonRequire(new_ref, module, conanfile,
                                               exports_folder, exports_sources_folder)
            self._cached_requires[ref] = python_require

        return python_require

    def __call__(self, reference):
        if not self.valid:
            raise ConanException("Invalid use of python_requires(%s)" % reference)
        try:
            python_req = self._look_for_require(reference)
            self._requires.append(python_req)
            return python_req.module
        except NotFoundException:
            raise ConanException('Unable to find python_requires("{}") in remotes'.format(reference))
