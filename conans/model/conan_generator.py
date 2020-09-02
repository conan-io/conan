from abc import ABCMeta, abstractproperty

import six

from conans.errors import ConanException
from conans.model.build_info import COMPONENT_SCOPE


@six.add_metaclass(ABCMeta)
class Generator(object):
    name = None

    def __init__(self, conanfile):
        self.conanfile = conanfile
        self.normalize = True
        self._deps_build_info = conanfile.deps_cpp_info
        self._deps_env_info = conanfile.deps_env_info
        self._env_info = conanfile.env_info
        self._deps_user_info = conanfile.deps_user_info
        self._user_info_build = getattr(conanfile, 'user_info_build', None)

    @classmethod
    def _get_name(cls, obj):
        return obj.get_name(cls.name)

    @property
    def deps_build_info(self):
        return self._deps_build_info

    @property
    def deps_env_info(self):
        return self._deps_env_info

    @property
    def deps_user_info(self):
        return self._deps_user_info

    @property
    def env_info(self):
        return self._env_info

    @property
    def settings(self):
        return self.conanfile.settings

    @abstractproperty
    def content(self):
        raise NotImplementedError()

    @abstractproperty
    def filename(self):
        raise NotImplementedError()

    def sorted_components(self, cpp_info):
        return cpp_info._get_sorted_components()

    def _validate_components(self, cpp_info):
        """ Check that all required components are provided by the dependencies """

        def _check_component_in_requirements(require):
            if COMPONENT_SCOPE in require:
                req_name, req_comp_name = require.split(COMPONENT_SCOPE)
                if req_name == req_comp_name:
                    return
                if req_comp_name not in self.deps_build_info[req_name].components:
                    raise ConanException("Component '%s' not found in '%s' package requirement"
                                         % (require, req_name))

        for comp_name, comp in cpp_info.components.items():
            for cmp_require in comp.requires:
                _check_component_in_requirements(cmp_require)

        # for pkg_require in cpp_info.requires:
        #     _check_component_in_requirements(pkg_require)

    def _get_components(self, pkg_name, cpp_info):
        self._validate_components(cpp_info)

        ret = []
        for comp_name, comp in self.sorted_components(cpp_info).items():
            comp_genname = self._get_name(cpp_info.components[comp_name])
            comp_requires_gennames = self._get_component_requires(pkg_name, comp)
            ret.append((comp_genname, comp, comp_requires_gennames))
        ret.reverse()
        return ret

    def _get_component_requires(self, pkg_name, comp):
        comp_requires = []
        for require in comp.requires:
            comp_require_pkg_name, comp_require_comp_name = pkg_name, require
            if COMPONENT_SCOPE in require:
                comp_require_pkg_name, comp_require_comp_name = require.split(COMPONENT_SCOPE)

            comp_require_pkg = self.deps_build_info[comp_require_pkg_name]
            comp_require_pkg_findname = self._get_name(comp_require_pkg)
            if comp_require_comp_name in comp_require_pkg.components:
                comp_require_comp_findname = self._get_name(comp_require_pkg.components[comp_require_comp_name])
            else:
                comp_require_comp_findname = comp_require_pkg_findname
            comp_requires.append((comp_require_pkg_findname, comp_require_comp_findname))
        return comp_requires
