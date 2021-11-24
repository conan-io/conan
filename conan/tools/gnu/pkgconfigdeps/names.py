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


class PkgConfigDepsRequires(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep
        self._aliases = {}

    def _save_aliases(self):
        """
        Get the property pkg_config_name given by a CppInfo or _NewComponent object and
        save all the possible aliases defined for that name.

        :param info_obj: <_NewComponent> or <_CppInfo> object
        :return: str or None
        """
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
        return pkg_config_name

    @property
    def components_requires_names(self):
        return

    @property
    def global_package_requires_names(self):
        return

    def
