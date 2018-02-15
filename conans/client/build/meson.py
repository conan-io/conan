import os

from conans import tools
from conans.client import join_arguments, defs_to_string
from conans.errors import ConanException
from conans.tools import args_to_string
from conans.util.files import mkdir


class Meson(object):

    def __init__(self, conanfile, backend=None, build_type=None):
        """
        :param conanfile: Conanfile instance (or settings for retro compatibility)
        :param backend: Generator name to use or none to autodetect.
               Possible values: ninja,vs,vs2010,vs2015,vs2017,xcode
        :param build_type: Overrides default build type comming from settings
        """
        self._conanfile = conanfile
        self._settings = conanfile.settings

        self._os = self._settings.get_safe("os")
        self._compiler = self._settings.get_safe("compiler")
        self._compiler_version = self._settings.get_safe("compiler.version")
        self._build_type = self._settings.get_safe("build_type")

        self.backend = backend or "ninja"  # Other backends are poorly supported, not default other.
        self.build_dir = None
        self.definitions = {}
        if build_type and build_type != self._build_type:
            # Call the setter to warn and update the definitions if needed
            self.build_type = build_type

    @property
    def build_type(self):
        return self._build_type

    @build_type.setter
    def build_type(self, build_type):
        settings_build_type = self._settings.get_safe("build_type")
        if build_type != settings_build_type:
            self._conanfile.output.warn(
                'Set build type "%s" is different than the settings build_type "%s"'
                % (build_type, settings_build_type))
        self._build_type = build_type
        self.definitions.update(self._build_type_definition())

    @property
    def build_folder(self):
        return self.build_dir

    @build_folder.setter
    def build_folder(self, value):
        self.build_dir = value

    @staticmethod
    def _get_dir(folder, origin):
        if folder:
            if os.path.isabs(folder):
                return folder
            return os.path.join(origin, folder)
        return origin

    def _get_dirs(self, source_folder, build_folder, source_dir, build_dir, cache_build_folder):
        if (source_folder or build_folder) and (source_dir or build_dir):
            raise ConanException("Use 'build_folder'/'source_folder'")

        if source_dir or build_dir:  # OLD MODE
            build_ret = build_dir or self.build_dir or self._conanfile.build_folder
            source_ret = source_dir or self._conanfile.source_folder
        else:
            build_ret = self._get_dir(build_folder, self._conanfile.build_folder)
            source_ret = self._get_dir(source_folder, self._conanfile.source_folder)

        if self._conanfile.in_local_cache and cache_build_folder:
            build_ret = self._get_dir(cache_build_folder, self._conanfile.build_folder)

        return source_ret, build_ret

    def configure(self, args=None, defs=None, source_dir=None, build_dir=None,
                  pkg_config_paths=None, cache_build_folder=None,
                  build_folder=None, source_folder=None):
        args = args or []
        defs = defs or {}

        source_dir, self.build_dir = self._get_dirs(source_folder, build_folder,
                                                    source_dir, build_dir,
                                                    cache_build_folder)

        if pkg_config_paths:
            pc_paths = os.pathsep.join(self._get_dir(f, self._conanfile.install_folder)
                                       for f in pkg_config_paths)
        else:
            pc_paths = self._conanfile.install_folder

        mkdir(self.build_dir)
        build_type = ("--buildtype=%s" % self.build_type if self.build_type else "").lower()
        arg_list = join_arguments([
            "--backend=%s" % self.backend,
            args_to_string(args),
            defs_to_string(defs),
            build_type
        ])
        command = 'meson "%s" "%s" %s' % (source_dir, self.build_dir, arg_list)
        command = self._append_vs_if_needed(command)
        with tools.environment_append({"PKG_CONFIG_PATH": pc_paths}):
            self._conanfile.run(command)

    def _append_vs_if_needed(self, command):
        if self._compiler == "Visual Studio" and self.backend == "ninja":
            command = "%s && %s" % (tools.vcvars_command(self._conanfile.settings), command)
        return command

    def build(self, args=None, build_dir=None, targets=None):
        if self.backend != "ninja":
            raise ConanException("Build only supported with 'ninja' backend")

        args = args or []
        build_dir = build_dir or self.build_dir or self._conanfile.build_folder

        arg_list = join_arguments([
            '-C "%s"' % build_dir,
            args_to_string(args),
            args_to_string(targets)
        ])
        command = "ninja %s" % arg_list
        command = self._append_vs_if_needed(command)
        self._conanfile.run(command)
