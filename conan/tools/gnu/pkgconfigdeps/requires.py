from collections import namedtuple

from conans.errors import ConanException


def get_pc_name(dep_name, comp_name):
    """Build a composed name for all the components and its package root name"""
    return "%s-%s" % (dep_name, comp_name)


def get_package_reference_name(dep):
    """Get the reference name for the given package"""
    # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
    #        Remove it for Conan 2.0
    return str(dep.ref.name)


def get_package_name_and_aliases(dep):
    """
    If user declares the property "pkg_config_name" as part of the global cpp_info,
    it'll be used as a complete alias for that package.
    """
    pkg_config_name = dep.cpp_info.get_property("pkg_config_name", "PkgConfigDeps")
    return pkg_config_name or get_package_reference_name(dep)


def get_component_name_and_aliases(dep, comp_name):
    """
    If user declares the property "pkg_config_name" as part of the cpp_info.components["comp_name"],
    it'll be used as a complete alias for that package component.
    """
    if comp_name not in dep.cpp_info.components:
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=get_package_reference_name,
                                                          cname=comp_name))
    comp_pkg_config_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name",
                                                                           "PkgConfigDeps")
    return comp_pkg_config_name


PkgConfigInfoComponent = namedtuple("PkgConfigInfoComponent", ['name', 'requires', 'cpp_info'])
PkgConfigInfoDependency = namedtuple('PkgConfigInfoDependency', ['name', 'requires'])
PkgConfigInfoAlias = namedtuple('PkgConfigInfoAlias', ['name', 'requires'])


class PkgConfigDepsRequires(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep

    def get_pkg_config_name(self, info_obj):
        """
        Get the property pkg_config_name given by a CppInfo or _NewComponent object and
        save all the possible aliases defined for that name.

        :param info_obj: <_NewComponent> or <_CppInfo> object
        :return: str or None
        """
        aliases = info_obj.get_property("pkg_config_name", "PkgConfigDeps")
        # if it's a list of names, let's save the other ones as pure aliases
        if isinstance(aliases, list):
            # The main pkg_config_name is the first one
            pkg_config_name = aliases[0]
            aliases = aliases[1:]
            if aliases:
                pkg_config_name_aliases[pkg_config_name] = aliases
                # Loop over the aliases defined to check any possible duplication
                for alias in aliases:
                    if alias in global_pkg_config_name_aliases:
                        self._out.warn("Alias name '%s' was already defined by any other package or "
                                       "component and it'll be overwritten." % alias)
                    else:
                        self._global_pkg_config_name_aliases.append(alias)
        else:
            pkg_config_name = aliases
        return pkg_config_name

    def get_component_requires_names(self, dep_name, cpp_info):
        """
        Get all the pkg-config valid names from the requires ones given a dependency and
        a CppInfo object.

        Note: CppInfo could be coming from one Component object instead of the dependency
        """
        ret = []
        for req in cpp_info.requires:
            pkg_name, comp_name = req.split("::") if "::" in req else (dep_name, req)
            # FIXME: it could allow defining requires to not direct dependencies
            req_conanfile = self._conanfile.dependencies.host[pkg_name]
            comp_alias_name = get_component_name(req_conanfile, comp_name)
            if not comp_alias_name:
                # Just in case, let's be sure about the pkg has any alias
                pkg_name = get_package_name(req_conanfile)
                comp_alias_name = get_pc_name(pkg_name, comp_name)
            ret.append(comp_alias_name)
        return ret

    @property
    def global_requires_names(self):
        """Get all the dependency's requirements (public dependencies and components)"""
        dep_name = get_package_reference_name(self._dep)
        # At first, let's check if we have defined some component requires, e.g., "pkg::cmp1"
        requires = self.get_component_requires_names(dep_name, self._dep.cpp_info)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct dependencies,
            # e.g., requires = "other_pkg/1.0"
            requires = [get_package_name(req) for req in self._dep.dependencies.direct_host.values()]
        return requires

    def load_components_info(self):
        # Loop through all the package's components
        for comp_name, comp_cpp_info in self._dep.cpp_info.get_sorted_components().items():
            comp_requires_names = self._get_component_requires_names(self._pkg_reference_name,
                                                                     comp_cpp_info)
            pkg_comp_name = self.get_component_name(self._dep, comp_name)
            if not pkg_comp_name:
                pkg_comp_name = self._get_pc_name(self._pkg_name, comp_name)

