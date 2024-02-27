import os

from conan.tools.build import build_jobs
from conan.tools.meson.mesondeps import MesonDeps
from conan.tools.meson.toolchain import MesonToolchain


class Meson(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def configure(self, reconfigure=False):
        if reconfigure:
            self._conanfile.output.warning("reconfigure param has been deprecated."
                                           " Removing in Conan 2.x.")
        source_folder = self._conanfile.source_folder
        build_folder = self._conanfile.build_folder
        cmd = "meson setup"
        generators_folder = self._conanfile.generators_folder
        cross = os.path.join(generators_folder, MesonToolchain.cross_filename)
        native = os.path.join(generators_folder, MesonToolchain.native_filename)
        deps_flags = os.path.join(generators_folder, MesonDeps.filename)  # extra machine files layer
        meson_filenames = []
        if os.path.exists(cross):
            cmd_param = " --cross-file"
            meson_filenames.append(cross)
        else:
            cmd_param = " --native-file"
            meson_filenames.append(native)

        if os.path.exists(deps_flags):
            meson_filenames.append(deps_flags)

        machine_files = self._conanfile.conf.get("tools.meson.mesontoolchain:extra_machine_files",
                                                 default=[], check_type=list)
        if machine_files:
            meson_filenames.extend(machine_files)

        cmd += "".join([f'{cmd_param} "{meson_option}"' for meson_option in meson_filenames])
        cmd += ' "{}" "{}"'.format(build_folder, source_folder)
        # Issue related: https://github.com/mesonbuild/meson/issues/12880
        cmd += ' --prefix=/'  # this must be an absolute path, otherwise, meson complains
        self._conanfile.output.info("Meson configure cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def build(self, target=None):
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson compile -C "{}"'.format(meson_build_folder)
        njobs = build_jobs(self._conanfile)
        if njobs:
            cmd += " -j{}".format(njobs)
        if target:
            cmd += " {}".format(target)
        self._conanfile.output.info("Meson build cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def install(self):
        meson_build_folder = self._conanfile.build_folder.replace("\\", "/")
        meson_package_folder = self._conanfile.package_folder.replace("\\", "/")
        # Assuming meson >= 0.57.0
        cmd = f'meson install -C "{meson_build_folder}" --destdir "{meson_package_folder}"'
        self._conanfile.run(cmd)

    def test(self):
        if self._conanfile.conf.get("tools.build:skip_test"):
            return
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson test -v -C "{}"'.format(meson_build_folder)
        # TODO: Do we need vcvars for test?
        # TODO: This should use conanrunenv, but what if meson itself is a build-require?
        self._conanfile.run(cmd)
