import os
import subprocess

from conans.client import defs_to_string, join_arguments, tools
from conans.client.tools.oss import args_to_string
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB, DEFAULT_SHARE
from conans.model.version import Version
from conans.util.files import decode_text, get_abs_path, mkdir


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

        self._os = self._ss("os")
        self._compiler = self._ss("compiler")
        self._compiler_version = self._ss("compiler.version")
        self._build_type = self._ss("build_type")

        self.backend = backend or "ninja"  # Other backends are poorly supported, not default other.

        self.options = dict()
        if self._conanfile.package_folder:
            self.options['prefix'] = self._conanfile.package_folder
        self.options['libdir'] = DEFAULT_LIB
        self.options['bindir'] = DEFAULT_BIN
        self.options['sbindir'] = DEFAULT_BIN
        self.options['libexecdir'] = DEFAULT_BIN
        self.options['includedir'] = DEFAULT_INCLUDE

        # C++ standard
        cppstd = self._ss("cppstd")
        cppstd_conan2meson = {
            None: 'none',
            '98': 'c++03', 'gnu98': 'gnu++03',
            '11': 'c++11', 'gnu11': 'gnu++11',
            '14': 'c++14', 'gnu14': 'gnu++14',
            '17': 'c++17', 'gnu17': 'gnu++17',
            '20': 'c++1z', 'gnu20': 'gnu++1z'
        }
        self.options['cpp_std'] = cppstd_conan2meson[cppstd]

        # shared
        shared = self._so("shared")
        self.options['default_library'] = "shared" if shared is None or shared else "static"

        # fpic
        if self._os and "Windows" not in self._os:
            fpic = self._so("fPIC")
            if fpic is not None:
                shared = self._so("shared")
                self.options['b_staticpic'] = "true" if (fpic or shared) else "false"

        self.build_dir = None
        if build_type and build_type != self._build_type:
            # Call the setter to warn and update the definitions if needed
            self.build_type = build_type

    def _ss(self, setname):
        """safe setting"""
        return self._conanfile.settings.get_safe(setname)

    def _so(self, setname):
        """safe option"""
        return self._conanfile.options.get_safe(setname)

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

    @property
    def build_folder(self):
        return self.build_dir

    @build_folder.setter
    def build_folder(self, value):
        self.build_dir = value

    def _get_dirs(self, source_folder, build_folder, source_dir, build_dir, cache_build_folder):
        if (source_folder or build_folder) and (source_dir or build_dir):
            raise ConanException("Use 'build_folder'/'source_folder'")

        if source_dir or build_dir:  # OLD MODE
            build_ret = build_dir or self.build_dir or self._conanfile.build_folder
            source_ret = source_dir or self._conanfile.source_folder
        else:
            build_ret = get_abs_path(build_folder, self._conanfile.build_folder)
            source_ret = get_abs_path(source_folder, self._conanfile.source_folder)

        if self._conanfile.in_local_cache and cache_build_folder:
            build_ret = get_abs_path(cache_build_folder, self._conanfile.build_folder)

        return source_ret, build_ret

    @property
    def flags(self):
        return defs_to_string(self.options)

    def configure(self, args=None, defs=None, source_dir=None, build_dir=None,
                  pkg_config_paths=None, cache_build_folder=None,
                  build_folder=None, source_folder=None):
        if not self._conanfile.should_configure:
            return
        args = args or []
        defs = defs or {}

        # overwrite default values with user's inputs
        self.options.update(defs)

        source_dir, self.build_dir = self._get_dirs(source_folder, build_folder,
                                                    source_dir, build_dir,
                                                    cache_build_folder)

        if pkg_config_paths:
            pc_paths = os.pathsep.join(get_abs_path(f, self._conanfile.install_folder)
                                       for f in pkg_config_paths)
        else:
            pc_paths = self._conanfile.install_folder

        mkdir(self.build_dir)

        bt = {"RelWithDebInfo": "debugoptimized",
              "MinSizeRel": "release",
              "Debug": "debug",
              "Release": "release"}.get(str(self.build_type), "")

        build_type = "--buildtype=%s" % bt
        arg_list = join_arguments([
            "--backend=%s" % self.backend,
            self.flags,
            args_to_string(args),
            build_type
        ])
        command = 'meson "%s" "%s" %s' % (source_dir, self.build_dir, arg_list)
        command = self._append_vs_if_needed(command)
        with tools.environment_append({"PKG_CONFIG_PATH": pc_paths}):
            self._conanfile.run(command)

    def _append_vs_if_needed(self, command):
        if self._compiler == "Visual Studio" and self.backend == "ninja":
            vcvars = tools.vcvars_command(self._conanfile.settings, output=self._conanfile.output)
            command = "%s && %s" % (vcvars, command)
        return command

    def build(self, args=None, build_dir=None, targets=None):
        if not self._conanfile.should_build:
            return
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

    def install(self, args=None, build_dir=None):
        if not self._conanfile.should_install:
            return
        mkdir(self._conanfile.package_folder)
        if not self.options.get('prefix'):
            raise ConanException("'prefix' not defined for 'meson.install()'\n"
                                 "Make sure 'package_folder' is defined")
        self.build(args=args, build_dir=build_dir, targets=["install"])

    def test(self, args=None, build_dir=None, targets=None):
        if not self._conanfile.should_test:
            return
        if not targets:
            targets = ["test"]
        self.build(args=args, build_dir=build_dir, targets=targets)

    @staticmethod
    def get_version():
        try:
            out, _ = subprocess.Popen(["meson", "--version"], stdout=subprocess.PIPE).communicate()
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.rsplit(' ', 1)[-1]
            return Version(version_str)
        except Exception as e:
            raise ConanException("Error retrieving Meson version: '{}'".format(e))
