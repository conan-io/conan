import os


def get_component_name(component, default):
    return component.get_property("qbs_module_name", "QbsDeps") or \
        default


def get_module_name(dependency):
    return get_component_name(dependency.cpp_info, dependency.ref.name)


def prepend_package_folder(paths, package_folder):
    return [os.path.join(package_folder, path) for path in paths]
