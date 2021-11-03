import os


def get_module_name(dependency):
    return dependency.cpp_info.get_property("qbs_module_name", "QbsDeps") or \
        dependency.ref.name


def get_component_name(component, default):
    return component.get_property("qbs_module_name", "QbsDeps") or \
        default


def prepent_package_folder(paths, package_folder):
    return [os.path.join(package_folder, path) for path in paths]
