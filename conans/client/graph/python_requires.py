import os
from contextlib import contextmanager

from conans.client.recorder.action_recorder import ActionRecorder
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement


class PyRequire(object):
    def __init__(self, module, conanfile, ref, path):
        self.module = module
        self.conanfile = conanfile
        self.ref = ref
        self.path = path


class PyRequires(object):
    """ this is the object that replaces the declared conanfile.py_requires"""
    def __init__(self):
        self._pyrequires = {}  # {pkg-name: PythonRequire}
        self._transitive = {}

    def update_transitive(self, conanfile):
        transitive = getattr(conanfile, "python_requires", None)
        if not transitive:
            return
        for name, transitive_py_require in transitive.all_items():
            existing = self._pyrequires.get(name)
            if existing and existing.ref != transitive_py_require.ref:
                raise ConanException("Conflict in py_requires %s - %s"
                                     % (existing.ref, transitive_py_require.ref))
            self._transitive[name] = transitive_py_require

    def all_items(self):
        new_dict = self._pyrequires.copy()
        new_dict.update(self._transitive)
        return new_dict.items()

    def all_refs(self):
        return ([r.ref for r in self._pyrequires.values()] +
                [r.ref for r in self._transitive.values()])

    def items(self):
        return self._pyrequires.items()

    def __getitem__(self, item):
        try:
            return self._pyrequires[item]
        except KeyError:
            raise ConanException("'%s' is not a python_require" % item)

    def __setitem__(self, key, value):
        # single item assignment, direct
        existing = self._pyrequires.get(key)
        if existing:
            raise ConanException("The python_require '%s' already exists" % key)
        self._pyrequires[key] = value


class PyRequireLoader(object):
    def __init__(self, proxy, range_resolver):
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._cached_py_requires = {}

    def enable_remotes(self, check_updates=False, update=False, remotes=None):
        self._check_updates = check_updates
        self._update = update
        self._remotes = remotes

    @contextmanager
    def capture_requires(self):
        # DO nothing, just to stay compatible with the interface of python_requires
        yield []

    def load_py_requires(self, conanfile, lock_python_requires, loader):
        if not hasattr(conanfile, "python_requires") or isinstance(conanfile.python_requires, dict):
            return
        py_requires_refs = conanfile.python_requires
        if isinstance(py_requires_refs, str):
            py_requires_refs = [py_requires_refs, ]

        py_requires = self._resolve_py_requires(py_requires_refs, lock_python_requires, loader)
        if hasattr(conanfile, "python_requires_extend"):
            py_requires_extend = conanfile.python_requires_extend
            if isinstance(py_requires_extend, str):
                py_requires_extend = [py_requires_extend, ]
            for p in py_requires_extend:
                pkg_name, base_class_name = p.rsplit(".", 1)
                base_class = getattr(py_requires[pkg_name].module, base_class_name)
                conanfile.__bases__ = (base_class,) + conanfile.__bases__
        conanfile.python_requires = py_requires

    def _resolve_py_requires(self, py_requires_refs, lock_python_requires, loader):
        result = PyRequires()
        for py_requires_ref in py_requires_refs:
            py_requires_ref = self._resolve_ref(py_requires_ref, lock_python_requires)
            try:
                py_require = self._cached_py_requires[py_requires_ref]
            except KeyError:
                conanfile, module, new_ref, path = self._load_pyreq_conanfile(loader,
                                                                              lock_python_requires,
                                                                              py_requires_ref)
                py_require = PyRequire(module, conanfile, new_ref, path)
                self._cached_py_requires[py_requires_ref] = py_require
            result[py_require.ref.name] = py_require
            # Update transitive and check conflicts
            result.update_transitive(py_require.conanfile)
        return result

    def _resolve_ref(self, py_requires_ref, lock_python_requires):
        ref = ConanFileReference.loads(py_requires_ref)
        if lock_python_requires:
            locked = {r.name: r for r in lock_python_requires}[ref.name]
            ref = locked
        else:
            requirement = Requirement(ref)
            self._range_resolver.resolve(requirement, "py_require", update=self._update,
                                         remotes=self._remotes)
            ref = requirement.ref
        return ref

    def _load_pyreq_conanfile(self, loader, lock_python_requires, ref):
        recipe = self._proxy.get_recipe(ref, self._check_updates, self._update,
                                        remotes=self._remotes, recorder=ActionRecorder())
        path, _, _, new_ref = recipe
        conanfile, module = loader.load_basic_module(path, lock_python_requires, user=new_ref.user,
                                                     channel=new_ref.channel)
        conanfile.name = new_ref.name
        # FIXME Conan 2.0 version should be a string, not a Version object
        conanfile.version = new_ref.version

        if getattr(conanfile, "alias", None):
            ref = ConanFileReference.loads(conanfile.alias)
            conanfile, module, new_ref, path = self._load_pyreq_conanfile(loader,
                                                                          lock_python_requires,
                                                                          ref)
        return conanfile, module, new_ref, os.path.dirname(path)
