from conan.tools.files import save
from conan.errors import ConanException
from conan.tools.env import VirtualBuildEnv
from conans.model.dependencies import get_transitive_requires
import json
import os


class _QbsDepsFile:
    def __init__(self, qbsdeps):
        self._qbsdeps = qbsdeps

    @property
    def filename(self):
        return None

    def get_content(self):
        return {}

    def render(self):
        return json.dumps(self.get_content(), indent=4)


class _QbsDepsCommonFile(_QbsDepsFile):
    def __init__(self, qbsdeps, format_version=1):
        super().__init__(qbsdeps)
        self._format_version = format_version

    @property
    def filename(self):
        return 'common.json'

    def get_content(self):
        env_vars = VirtualBuildEnv(self._qbsdeps._conanfile).vars()
        build_env = {k: v for k, v in env_vars.items()}
        return {'build_env': build_env, 'format_version': self._format_version}


class _QbsDepsModuleFile(_QbsDepsFile):
    def __init__(self, qbsdeps, dep, component, deps, moduleName):
        super().__init__(qbsdeps)
        self._dep = dep
        self._component = component
        self._deps = deps
        self._moduleName = moduleName

    @property
    def filename(self):
        return os.path.join('modules', self._moduleName + '.json')

    def get_content(self):
        return {
            'package_name': self._dep.ref.name,
            'version': str(self._dep.ref.version),
            'cpp_info': self._component.serialize(),
            'dependencies': [{'name': n, "version": str(v)} for n, v in self._deps],
            'settings': {k: v for k, v in self._dep.settings.items()},
            'options': {k: v for k, v in self._dep.options.items()}
        }


class QbsDeps:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def content(self):
        qbs_files = []
        qbs_files.append(_QbsDepsCommonFile(self))

        for require, dep in self._conanfile.dependencies.items():

            # skip build deps for now
            if require.build:
                continue

            transitive_reqs = get_transitive_requires(self._conanfile, dep)

            def _get_package_name(dep):
                # TODO: pkgconfig uses suffix, do we need it?
                # see https://github.com/conan-io/conan/blob/develop2/conan/tools/gnu/pkgconfigdeps.py#L319
                return dep.cpp_info.get_property("pkg_config_name") or dep.ref.name

            def _get_component_name(dep, comp_name):
                if comp_name not in dep.cpp_info.components:
                    if dep.ref.name == comp_name:
                        return _get_package_name(dep)
                    raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                         "package requirement".format(name=dep.ref.name,
                                                                      cname=comp_name))

                # TODO: pkgconfig uses suffix, do we need it?
                pkg_config_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name")
                return pkg_config_name or comp_name

            def _get_name_with_namespace(namespace, name):
                """
                Build a name with a namespace, e.g., openssl-crypto
                """
                return f"{namespace}-{name}"

            def get_components(dep):
                ret = {}
                for comp_ref_name, info in dep.cpp_info.get_sorted_components().items():
                    comp_name = _get_component_name(dep, comp_ref_name)
                    ret[comp_name] = info
                return ret

            # copy & paste from pkgconfig
            # TODO: versions
            def get_cpp_info_requires_names(dep, cpp_info):
                ret = []
                dep_ref_name = dep.ref.name
                for req in cpp_info.requires:
                    pkg_ref_name, comp_ref_name = (
                        req.split("::") if "::" in req else (dep_ref_name, req)
                    )

                    if dep_ref_name != pkg_ref_name:
                        try:
                            req_conanfile = transitive_reqs[pkg_ref_name]
                        except KeyError:
                            # If the dependency is not in the transitive, might be skipped
                            continue
                    # For instance, dep == "hello/1.0" and req == "hello::cmp1" -> hello == hello
                    else:
                        req_conanfile = dep

                    comp_name = _get_component_name(req_conanfile, comp_ref_name)
                    if not comp_name:
                        pkg_name = _get_package_name(req_conanfile)
                        # Creating a component name with namespace, e.g., dep-comp1
                        comp_name = _get_name_with_namespace(pkg_name, comp_ref_name)
                    ret.append((comp_name, req_conanfile.ref.version))
                return ret

            if not dep.cpp_info.has_components:
                moduleName = _get_package_name(dep)
                requires = get_cpp_info_requires_names(dep, dep.cpp_info._package)
                if not requires:
                    # If no requires were found, let's try to get all the direct visible
                    # dependencies, e.g., requires = "other_pkg/1.0"
                    for deprequire, _ in dep.dependencies.direct_host.items():
                        requires.append((deprequire.ref.name, deprequire.ref.version))
                file = _QbsDepsModuleFile(self, dep, dep.cpp_info._package, requires, moduleName)
                qbs_files.append(file)
            else:
                full_requires = []
                for moduleName, component in get_components(dep).items():
                    requires = get_cpp_info_requires_names(dep, component)
                    qbs_files.append(_QbsDepsModuleFile(self, dep, component, requires, moduleName))
                    full_requires.append((moduleName, dep.ref.version))
                file = _QbsDepsModuleFile(
                    self, dep, dep.cpp_info._package, full_requires, _get_package_name(dep))
                qbs_files.append(file)

        return {file.filename: file for file in qbs_files}

    def generate(self):
        for file_name, qbs_deps_file in self.content.items():
            save(self._conanfile, os.path.join('qbs-deps', file_name), qbs_deps_file.render())
