from collections import namedtuple

from conans.errors import ConanException


def _get_name_with_namespace(namespace, name):
    """Build a name with a namespace, e.g., openssl-crypto"""
    return "%s-%s" % (namespace, name)


def _get_package_reference_name(dep):
    """Get the reference name for the given package"""
    # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
    #        Remove it for Conan 2.0
    return str(dep.ref.name)


def _get_package_aliases(dep):
    pkg_aliases = dep.cpp_info.get_property("pkg_config_aliases", "PkgConfigDeps")
    return pkg_aliases or []


def _get_component_aliases(dep, comp_name):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if dep.ref.name == comp_name:
            return _get_package_aliases(dep)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_aliases = dep.cpp_info.components[comp_name].get_property("pkg_config_aliases",
                                                                   "PkgConfigDeps")
    return comp_aliases or []


def _get_package_name(dep):
    pkg_name = dep.cpp_info.get_property("pkg_config_name", "PkgConfigDeps")
    return pkg_name or _get_package_reference_name(dep)


def _get_component_name(dep, comp_name):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if dep.ref.name == comp_name:
            return _get_package_name(dep)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name", "PkgConfigDeps")
    return comp_name


_PCInfoComponent = namedtuple("PCInfoComponent", ['name', 'requires', 'cpp_info', 'ref_name'])
_PCInfoPackage = namedtuple('PCInfoPackage', ['name', 'requires'])


class PCInfoLoader(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep
        self._pkg_name = _get_package_name(dep)
        self._pkg_ref_name = _get_package_reference_name(dep)
        # Initialized variables
        self._pkg_info = None
        self._components_info = []
        self._aliases_info = {}

    @property
    def package_info(self):
        return self._pkg_info

    @property
    def components_info(self):
        return self._components_info

    @property
    def aliases_info(self):
        return self._aliases_info

    def _get_component_requires_names(self, cpp_info):
        """
        Get all the pkg-config valid names from the requires ones given a dependency and
        a CppInfo object.

        Note: CppInfo could be coming from one Component object instead of the dependency
        """
        ret = []
        for req in cpp_info.requires:
            pkg_ref_name, comp_ref_name = req.split("::") if "::" in req \
                                                          else (self._pkg_ref_name, req)
            # FIXME: it could allow defining requires to not direct dependencies
            req_conanfile = self._conanfile.dependencies.host[pkg_ref_name]
            comp_name = _get_component_name(req_conanfile, comp_ref_name)
            if not comp_name:
                pkg_name = _get_package_name(req_conanfile)
                comp_name = _get_name_with_namespace(pkg_name, comp_ref_name)
            ret.append(comp_name)
        return ret

    def load_single_package_info(self):
        """Get all the dependency's requirements (public dependencies and components)"""
        # At first, let's check if we have defined some component requires, e.g., "pkg::cmp1"
        requires = self._get_component_requires_names(self._dep.cpp_info)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct dependencies,
            # e.g., requires = "other_pkg/1.0"
            requires = [_get_package_name(req)
                        for req in self._dep.dependencies.direct_host.values()]
        # Save the package information
        self._pkg_info = _PCInfoPackage(self._pkg_name, requires)

    def load_package_with_components_info(self):
        pkg_requires = []
        # Loop through all the package's components
        for comp_name, comp_cpp_info in self._dep.cpp_info.get_sorted_components().items():
            comp_requires_names = self._get_component_requires_names(comp_cpp_info)
            pkg_comp_name = _get_component_name(self._dep, comp_name)
            if not pkg_comp_name:
                pkg_comp_name = _get_name_with_namespace(self._pkg_name, comp_name)
            pkg_requires.append(pkg_comp_name)
            # Save each component information
            comp_info = _PCInfoComponent(pkg_comp_name, comp_requires_names, comp_cpp_info, comp_name)
            self._components_info.append(comp_info)
        # Save the package information
        self._pkg_info = _PCInfoPackage(self._pkg_name, pkg_requires)

    def load_aliases_info(self):
        # Component aliases
        for comp_info in self._components_info:
            comp_aliases = _get_component_aliases(self._dep, comp_info.ref_name)
            if comp_aliases:
                self._aliases_info[comp_info.name] = comp_aliases
        # Package aliases
        if self._pkg_info:
            pkg_aliases = _get_package_aliases(self._dep)
            if pkg_aliases:
                self._aliases_info[self._pkg_info.name] = pkg_aliases
