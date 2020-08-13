from abc import ABCMeta, abstractproperty

import six


@six.add_metaclass(ABCMeta)
class Generator(object):

    def __init__(self, conanfile):
        self.conanfile = conanfile
        self.normalize = True
        self._deps_build_info = conanfile.deps_cpp_info
        self._deps_env_info = conanfile.deps_env_info
        self._env_info = conanfile.env_info
        self._deps_user_info = conanfile.deps_user_info
        self._user_info_build = getattr(conanfile, 'user_info_build', None)

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
