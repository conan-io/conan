from collections import namedtuple

from conans.errors import ConanException


_PCInfoComponent = namedtuple("PCInfoComponent", ['name', 'requires', 'cpp_info', 'ref_name'])
_PCInfoPackage = namedtuple('PCInfoPackage', ['name', 'requires'])


def _get_name_with_namespace(namespace, name):
    """Build a name with a namespace, e.g., openssl-crypto"""
    return "%s-%s" % (namespace, name)


def _get_package_reference_name(dep):
    """Get the reference name for the given package"""
    # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
    #        Remove it for Conan 2.0
    return str(dep.ref.name)


def _get_package_aliases(dep):
    pkg_aliases = dep.cpp_info.get_property("pkg_config_aliases")
    return pkg_aliases or []


def _get_component_aliases(dep, comp_name):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if dep.ref.name == comp_name:
            return _get_package_aliases(dep)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_aliases = dep.cpp_info.components[comp_name].get_property("pkg_config_aliases")
    return comp_aliases or []


def _get_package_name(dep):
    pkg_name = dep.cpp_info.get_property("pkg_config_name")
    return pkg_name or _get_package_reference_name(dep)


def _get_component_name(dep, comp_name):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if dep.ref.name == comp_name:
            return _get_package_name(dep)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name")
    return comp_name


def _get_component_requires_names(dep, cpp_info):
    """
    Get all the pkg-config valid names from the requires ones given a dependency and
    a CppInfo object.

    Note: CppInfo could be coming from one Component object instead of the dependency
    """
    dep_ref_name = _get_package_reference_name(dep)
    ret = []
    for req in cpp_info.requires:
        pkg_ref_name, comp_ref_name = req.split("::") if "::" in req \
                                                      else (dep_ref_name, req)
        if dep_ref_name != pkg_ref_name:
            req_conanfile = dep.dependencies.host[pkg_ref_name]
        else:
            req_conanfile = dep
        comp_name = _get_component_name(req_conanfile, comp_ref_name)
        if not comp_name:
            pkg_name = _get_package_name(req_conanfile)
            comp_name = _get_name_with_namespace(pkg_name, comp_ref_name)
        ret.append(comp_name)
    return ret


def get_single_package_info(dep):
    """
    Get the whole package information when it does not have components declared
    """
    pkg_name = _get_package_name(dep)
    # At first, let's check if we have defined some component requires, e.g., "pkg::cmp1"
    requires = _get_component_requires_names(dep, dep.cpp_info)
    # If we have found some component requires it would be enough
    if not requires:
        # If no requires were found, let's try to get all the direct dependencies,
        # e.g., requires = "other_pkg/1.0"
        requires = [_get_package_name(req) for req in dep.dependencies.direct_host.values()]
    # Save the package information
    pkg_info = _PCInfoPackage(pkg_name, requires)
    return pkg_info


def get_package_with_components_info(dep):
    """
    Get the whole package and its components information like their own requires, names and even
    the cpp_info for each component.
    """
    pkg_name = _get_package_name(dep)
    pkg_requires = []
    components_info = []
    # Loop through all the package's components
    for comp_name, comp_cpp_info in dep.cpp_info.get_sorted_components().items():
        comp_requires_names = _get_component_requires_names(dep, comp_cpp_info)
        pkg_comp_name = _get_component_name(dep, comp_name)
        if not pkg_comp_name:
            pkg_comp_name = _get_name_with_namespace(pkg_name, comp_name)
        pkg_requires.append(pkg_comp_name)
        # Save each component information
        comp_info = _PCInfoComponent(pkg_comp_name, comp_requires_names, comp_cpp_info, comp_name)
        components_info.append(comp_info)
    # Save the package information
    pkg_info = _PCInfoPackage(pkg_name, pkg_requires)
    return pkg_info, components_info


def get_aliases_info(dep, package_info, components_info):
    """
    Get the whole aliases information for the given package and components names already calculated
    """
    aliases_info = {}
    # Package aliases
    if package_info:
        pkg_aliases = _get_package_aliases(dep)
        if pkg_aliases:
            aliases_info[package_info.name] = pkg_aliases
    # Component aliases
    for comp_info in components_info:
        comp_aliases = _get_component_aliases(dep, comp_info.ref_name)
        if comp_aliases:
            aliases_info[comp_info.name] = comp_aliases
    return aliases_info
