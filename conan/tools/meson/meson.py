import os

from conan.tools.build import build_jobs
from conan.tools.meson.toolchain import MesonToolchain
from conan.tools.meson.mesondeps import MesonDeps


class Meson(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def configure(self, reconfigure=False):
        source_folder = self._conanfile.source_folder
        build_folder = self._conanfile.build_folder
        cmd = "meson setup"
        generators_folder = self._conanfile.generators_folder
        cross = os.path.join(generators_folder, MesonToolchain.cross_filename)
        native = os.path.join(generators_folder, MesonToolchain.native_filename)
        deps_flags = os.path.join(generators_folder, MesonDeps.filename)  # extra machine files layer
        has_deps_flags = os.path.exists(deps_flags)

        if os.path.exists(cross):
            cmd += f' --cross-file "{cross}"'
            if has_deps_flags:
                cmd += f' --cross-file "{deps_flags}"'
        else:
            cmd += f' --native-file "{native}"'
            if has_deps_flags:
                cmd += f' --native-file "{deps_flags}"'

        cmd += f' "{build_folder}" "{source_folder}"'
        if self._conanfile.package_folder:
            cmd += f' -Dprefix="{self._conanfile.package_folder}"'
        if reconfigure:
            cmd += f' --reconfigure'
        self._conanfile.output.info(f"Meson configure cmd: {cmd}")
        self._conanfile.run(cmd)

    def build(self, target=None):
        meson_build_folder = self._conanfile.build_folder
        cmd = f'meson compile -C "{meson_build_folder}"'
        njobs = build_jobs(self._conanfile)
        if njobs:
            cmd += f" -j{njobs}"
        if target:
            cmd += f" {target}"
        self._conanfile.output.info(f"Meson build cmd: {cmd}")
        self._conanfile.run(cmd)

    def install(self):
        # To fix the destination package-folder
        if self._conanfile.package_folder:
            cmd = f'meson configure "{self._conanfile.build_folder}" -Dprefix="{self._conanfile.package_folder}"'
            self._conanfile.run(cmd)
            self._conanfile.output.info(f"Meson configure (prefix) cmd: {cmd}")
        meson_build_folder = self._conanfile.build_folder
        cmd = f'meson install -C "{meson_build_folder}"'
        self._conanfile.run(cmd)

    def test(self):
        if self._conanfile.conf.get("tools.build:skip_test"):
            return
        meson_build_folder = self._conanfile.build_folder
        cmd = f'meson test -v -C "{meson_build_folder}"'
        # TODO: Do we need vcvars for test?
        # TODO: This should use conanrunenv, but what if meson itself is a build-require?
        self._conanfile.run(cmd)
