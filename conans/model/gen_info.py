import os


from conans.errors import ConanException


class GenInfo(object):
    """ Object that stores generator specific options.
    It is intended to be system independent, translation to
    specific systems will be produced from this info
    """
    def __init__(self, cpp_info):
        self._cpp_info = cpp_info
        self._generators = {}

    def __getitem__(self, name):
        try:
            return self._generators[name]
        except KeyError:
            geninfo = self._construct_geninfo(name)
            self._generators[name] = geninfo
            return geninfo

    def _construct_geninfo(self, name):
        try:
            cls = {
                "cmake_find_package": CMakeFindPackageGenInfo,
                "cmake_find_package_multi": CMakeFindPackageMultiGenInfo,
                "pkg_config": PkgConfigGenInfo,
            }[name]
        except KeyError:
            raise ConanException("The generator '{}' does not support generator specific options".format(name))
        return cls(self._cpp_info)


class CMakeFindPackageGenInfo(object):
    def __init__(self, cpp_info):
        self._targets = _CMakeFindPackageGenInfoTargetsCollection(cpp_info)

    @property
    def targets(self):
        return self._targets


class _CMakeFindPackageGenInfoTargetsCollection(object):
    def __init__(self, cpp_info):
        self._cpp_info = cpp_info
        self._targets = {}

    def __getitem__(self, name):
        try:
            return self._targets[name]
        except KeyError:
            target = _CMakeFindPackageTarget(name, self._cpp_info)
            self._targets[name] = target
            return target

    def __iter__(self):
        return iter(self._targets.values())


class _CMakeFindPackageTarget(object):
    def __init__(self, name, cpp_info):
        self.name = name
        self._cpp_info = cpp_info
        for member in self._members:
            setattr(self, member, ModificationTrackingList())
        # FIXME: use/refactor CppInfo() such that:
        # - use specialization values if a value is given
        # - use the parameters of the main cpp_info
        # self._cpp_info = CppInfo()

    _members = []

    @classmethod
    def _add_property(cls, name):
        """Add a new property that will return self._cpp_info's properties if those were not modified"""
        member = "_" + name
        cls._members.append(member)

        def get_prop(self):
            mod_libs = getattr(self, member)
            if mod_libs.unmodified:
                return getattr(self._cpp_info, name)
            return getattr(self, member).getvalue()

        def set_prop(self, newval):
            getattr(self, member).setvalue(newval)

        setattr(cls, name, property(get_prop, set_prop))

    @classmethod
    def _add_final_prop_paths(cls, name, dep):
        """Add a new read-only property that returns absolute paths.
        The property name will be the absolute equivalent of dep."""
        depmember = "_" + dep

        def get_inner(self):
            mod_list = getattr(self, depmember)
            if mod_list.unmodified:
                return getattr(self._cpp_info, name)
            else:
                return self._cpp_info._filter_paths(mod_list.getvalue())

        setattr(cls, name, property(get_inner))

    @property
    def build_paths(self):
        # FIXME: required for conans.client.generators.cmake.DepsCppCmake
        # ==> this class should be split
        return []

    @property
    def build_modules_paths(self):
        # FIXME: required for conans.client.generators.cmake.DepsCppCmake
        # ==> this class should be split
        return []

    @property
    def rootpath(self):
        # Required for conans.client.generators.cmake.DepsCppCmake
        return self._cpp_info.rootpath


# Add read/write properties that recipes can modify
_CMakeFindPackageTarget._add_property("includedirs")
_CMakeFindPackageTarget._add_property("libdirs")
_CMakeFindPackageTarget._add_property("bindirs")
_CMakeFindPackageTarget._add_property("resdirs")
_CMakeFindPackageTarget._add_property("srcdirs")
_CMakeFindPackageTarget._add_property("frameworkdirs")

_CMakeFindPackageTarget._add_property("libs")
_CMakeFindPackageTarget._add_property("system_libs")
_CMakeFindPackageTarget._add_property("frameworks")
_CMakeFindPackageTarget._add_property("defines")
_CMakeFindPackageTarget._add_property("cxxflags")
_CMakeFindPackageTarget._add_property("cflags")
_CMakeFindPackageTarget._add_property("sharedlinkflags")
_CMakeFindPackageTarget._add_property("exelinkflags")


# These read-only properties are meant for the generators
_CMakeFindPackageTarget._add_final_prop_paths("include_paths", "includedirs")
_CMakeFindPackageTarget._add_final_prop_paths("lib_paths", "libdirs")
_CMakeFindPackageTarget._add_final_prop_paths("bin_paths", "bindirs")
_CMakeFindPackageTarget._add_final_prop_paths("res_paths", "resdirs")
_CMakeFindPackageTarget._add_final_prop_paths("src_paths", "srcdirs")
_CMakeFindPackageTarget._add_final_prop_paths("framework_paths", "frameworkdirs")


class ModificationTrackingList(object):
    """List that detects modification.
    In case of no modification, this allows returning a default value or pass through to a parent."""
    def __init__(self):
        self._v = self._NOTHING
        self._d = list()

    """Constant to denote nothing has changed."""
    _NOTHING = object()

    @property
    def unmodified(self):
        return self._v is self._NOTHING

    def getvalue(self):
        """Get the current list value"""
        if self._d and self.unmodified:
            self._v = self._d
        return self._v if self._v is not self._NOTHING else self._d

    def setvalue(self, value):
        self._v = self._d = value

# FIXME: TODO
class CMakeFindPackageMultiGenInfo(object):
    pass


#FIXME: TODO
class PkgConfigGenInfo(object):
    pass

