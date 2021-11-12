import json

import conan.tools.qbs.utils as utils


class QbsConanModuleProviderInfoTemplate(object):
    def __init__(self, qbsdeps, requires, dependencies):
        self.qbsdeps = qbsdeps
        self.requires = requires
        self.dependencies = dependencies

    def render(self):
        info = []

        for dep in self.dependencies:
            obj = {}
            obj["name"] = utils.get_module_name(dep)

            env = {}
            env["build"] = {k: v for k, v in dep.buildenv_info.vars(
                self.qbsdeps._conanfile).items()}
            env["run"] = {k: v for k, v in dep.runenv_info.vars(self.qbsdeps._conanfile).items()}
            env["deps"] = self.qbsdeps._conanfile.deps_env_info[dep.ref.name].vars
            obj["env"] = env

            components = []
            if dep.cpp_info.has_components:
                for comp_name in dep.cpp_info.component_names:
                    components.append(self.create_component(
                        dep, dep.cpp_info.components[comp_name], comp_name))
            else:
                components.append(self.create_component(
                    dep, dep.cpp_info, None))
            obj["components"] = components
            info.append(obj)

        return json.dumps(info, indent=2)

    @ property
    def filename(self):
        return "qbs-conanmoduleprovider-info.json"

    def create_component(self, dep, component, comp_name):
        comp = {}
        comp["name"] = None if comp_name is None else utils.get_component_name(component, comp_name)
        comp["bindirs"] = utils.prepend_package_folder(
            component.bindirs, dep.package_folder)
        return comp
