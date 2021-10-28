import os

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

    def all_refs(self):
        return [r.ref for r in self._pyrequires.values()]

    def items(self):
        return self._pyrequires.items()

    def __getitem__(self, item):
        try:
            return self._pyrequires[item]
        except KeyError:
            raise ConanException("'%s' is not a python_require" % item)

    def add_pyrequire(self, py_require):
        key = py_require.ref.name
        # single item assignment, direct
        existing = self._pyrequires.get(key)
        if existing:
            raise ConanException("The python_require '%s' already exists" % key)
        self._pyrequires[key] = py_require

        transitive = getattr(py_require.conanfile, "python_requires", None)
        if transitive is None:
            return
        for name, transitive_py_require in transitive.items():
            existing = self._pyrequires.get(name)
            if existing and existing.ref != transitive_py_require.ref:
                raise ConanException("Conflict in py_requires %s - %s"
                                     % (existing.ref, transitive_py_require.ref))
            self._pyrequires[name] = transitive_py_require


class PyRequireLoader(object):
    def __init__(self, proxy, range_resolver):
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._cached_py_requires = {}

    def load_py_requires(self, conanfile, loader, graph_lock=None):
        py_requires_refs = getattr(conanfile, "python_requires", None)
        if py_requires_refs is None:
            return
        if isinstance(py_requires_refs, str):
            py_requires_refs = [py_requires_refs, ]

        py_requires = self._resolve_py_requires(py_requires_refs, graph_lock, loader)
        if hasattr(conanfile, "python_requires_extend"):
            py_requires_extend = conanfile.python_requires_extend
            if isinstance(py_requires_extend, str):
                py_requires_extend = [py_requires_extend, ]
            for p in py_requires_extend:
                pkg_name, base_class_name = p.rsplit(".", 1)
                base_class = getattr(py_requires[pkg_name].module, base_class_name)
                conanfile.__bases__ = (base_class,) + conanfile.__bases__
        conanfile.python_requires = py_requires

    def _resolve_py_requires(self, py_requires_refs, graph_lock, loader):
        result = PyRequires()
        for py_requires_ref in py_requires_refs:
            py_requires_ref = self._resolve_ref(py_requires_ref, graph_lock)
            try:
                py_require = self._cached_py_requires[py_requires_ref]
            except KeyError:
                conanfile, module, new_ref, path = self._load_pyreq_conanfile(loader,
                                                                              graph_lock,
                                                                              py_requires_ref)
                py_require = PyRequire(module, conanfile, new_ref, path)
                self._cached_py_requires[py_requires_ref] = py_require
            result.add_pyrequire(py_require)
        return result

    def _resolve_ref(self, py_requires_ref, graph_lock):
        ref = ConanFileReference.loads(py_requires_ref)
        requirement = Requirement(ref)
        if graph_lock:
            graph_lock.resolve_locked_pyrequires(requirement)
            # FIXME: Matching by name is not enough, should resolve ranges, etc.
            ref = requirement.ref
        else:
            alias = requirement.alias
            if alias is not None:
                ref = alias
            else:
                resolved_ref = self._range_resolver.resolve(requirement, "py_require")
                ref = resolved_ref
        return ref

    def _load_pyreq_conanfile(self, loader, graph_lock, ref):
        recipe = self._proxy.get_recipe(ref)
        path, _, _, new_ref = recipe
        conanfile, module = loader.load_basic_module(path, graph_lock)
        conanfile.name = new_ref.name
        # FIXME Conan 2.0 version should be a string, not a Version object
        conanfile.version = new_ref.version
        conanfile.user = new_ref.user
        # TODO: Is tihs really necessary?
        conanfile.channel = new_ref.channel

        if getattr(conanfile, "alias", None):
            ref = ConanFileReference.loads(conanfile.alias)
            requirement = Requirement(ref)
            alias = requirement.alias
            if alias is not None:
                ref = alias
            conanfile, module, new_ref, path = self._load_pyreq_conanfile(loader,
                                                                          graph_lock,
                                                                          ref)
        return conanfile, module, new_ref, os.path.dirname(path)
