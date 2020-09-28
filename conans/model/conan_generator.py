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

    def get_public_deps(self, cpp_info):
        return cpp_info.public_deps


class GeneratorComponentsMixin(object):

    @classmethod
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

        for pkg_require in cpp_info.requires:
            _check_component_in_requirements(pkg_require)

    def _get_require_name(self, pkg_name, req):
        pkg, cmp = req.split(COMPONENT_SCOPE) if COMPONENT_SCOPE in req else (pkg_name, req)
        pkg_build_info = self.deps_build_info[pkg]
        pkg_name = self._get_name(pkg_build_info)
        if cmp in pkg_build_info.components:
            cmp_name = self._get_name(pkg_build_info.components[cmp])
        else:
            cmp_name = pkg_name
        return pkg_name, cmp_name

    def _get_components(self, pkg_name, cpp_info):
        ret = []
        for comp_name, comp in self.sorted_components(cpp_info).items():
            comp_genname = self._get_name(cpp_info.components[comp_name])
            comp_requires_gennames = []
            for require in comp.requires:
                comp_requires_gennames.append(self._get_require_name(pkg_name, require))
            ret.append((comp_genname, comp, comp_requires_gennames))
        ret.reverse()
        return ret

    @classmethod
    def get_public_deps(cls, cpp_info):
        if cpp_info.requires:
            deps = [it for it in cpp_info.requires if COMPONENT_SCOPE in it]
            return [it.split(COMPONENT_SCOPE) for it in deps]
        else:
            return [(it, it) for it in cpp_info.public_deps]
