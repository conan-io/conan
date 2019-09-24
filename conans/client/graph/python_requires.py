from collections import namedtuple
from contextlib import contextmanager

from conans.client.loader import parse_conanfile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement
from conans.errors import ConanException, NotFoundException

PythonRequire = namedtuple("PythonRequire", ["ref", "module", "conanfile",
                                             "exports_folder", "exports_sources_folder"])


class PyRequires(object):
    """ this is the object that replaces the declared conanfile.py_requires"""
    def __init__(self):
        self._pyrequires = {}  # {pkg-name: module}

    def __getattr__(self, item):
        try:
            return self._pyrequires[item]
        except KeyError:
            raise ConanException("'%s' is not a py_require" % item)

    def __setitem__(self, key, value):
        # single item assignment, direct
        existing = self._pyrequires.get(key)
        if existing:
            raise ConanException("The py_requires '%s' already exists" % key)
        self._pyrequires[key] = value


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
        # DO nothing, just to stay compatible with the interface of python_requires
        yield []

    def load_py_requires(self, conanfile, lock_python_requires, loader):
        if not hasattr(conanfile, "py_requires"):
            return
        py_requires_refs = conanfile.py_requires
        if isinstance(py_requires_refs, str):
            py_requires_refs = [py_requires_refs, ]

        if lock_python_requires and not isinstance(lock_python_requires, dict):
            lock_python_requires = {r.name: r for r in lock_python_requires}
        py_requires, all_refs = self._resolve_py_requires(py_requires_refs, lock_python_requires,
                                                          loader)
        if hasattr(conanfile, "py_requires_extend"):
            py_requires_extend = conanfile.py_requires_extend
            if isinstance(py_requires_extend, str):
                py_requires_extend = [py_requires_extend, ]
            for p in py_requires_extend:
                pkg_name, base_class_name = p.split(".")
                base_class = getattr(getattr(py_requires, pkg_name), base_class_name)
                conanfile.__bases__ = (base_class,) + conanfile.__bases__
        conanfile.py_requires = py_requires
        conanfile.py_requires_all_refs = all_refs

    def _resolve_py_requires(self, py_requires_refs, lock_python_requires, loader):
        result = PyRequires()
        all_refs = {}
        for py_requires_ref in py_requires_refs:
            conanfile, module, new_ref = self._load_conanfile(loader, lock_python_requires,
                                                              py_requires_ref)
            result[new_ref.name] = module
            # Update the list of transitive, detecting conflicts
            existing = all_refs.get(new_ref.name)
            if existing and existing != new_ref:
                raise ConanException("Conflict in py_requires %s - %s" % (existing, new_ref))
            all_refs[new_ref.name] = new_ref
            for name, ref in getattr(conanfile, "py_requires_all_refs", {}).items():
                existing = all_refs.get(name)
                if existing and existing != ref:
                    raise ConanException("Conflict in py_requires %s - %s" % (existing, ref))
                all_refs[name] = ref
        return result, all_refs

    def _load_conanfile(self, loader, lock_python_requires, py_requires_ref):
        ref = ConanFileReference.loads(py_requires_ref)
        if lock_python_requires:
            locked = lock_python_requires[ref.name]
            ref = locked
        else:
            requirement = Requirement(ref)
            self._range_resolver.resolve(requirement, "py_require", update=self._update,
                                         remotes=self._remotes)
            ref = requirement.ref
        recipe = self._proxy.get_recipe(ref, self._check_updates, self._update,
                                        remotes=self._remotes, recorder=ActionRecorder())
        path, _, _, new_ref = recipe
        conanfile, module = loader.load_class_module(conanfile_path=path,
                                                     lock_python_requires=lock_python_requires)
        if getattr(conanfile, "alias", None):
            conanfile, module, new_ref = self._load_conanfile(loader, lock_python_requires,
                                                              conanfile.alias)
        return conanfile, module, new_ref


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
