import os
import textwrap
import traceback
from os.path import join

from conans.errors import ConanException, conanfile_exception_formatter
from conans.util.env_reader import get_env
from conans.util.files import normalize, save, mkdir
from .deploy import DeployGenerator
from ..tools import chdir


class GeneratorManager(object):
    def __init__(self):
        self._generators = {"deploy": DeployGenerator}
        self._new_generators = ["CMakeToolchain", "CMakeDeps", "MSBuildToolchain",
                                "MesonToolchain", "MSBuildDeps", "QbsToolchain", "msbuild",
                                "VirtualRunEnv", "VirtualBuildEnv", "AutotoolsDeps",
                                "AutotoolsToolchain", "BazelDeps", "BazelToolchain", "PkgConfigDeps",
                                "VCVars"]

    def add(self, name, generator_class, custom=False):
        if name not in self._generators or custom:
            self._generators[name] = generator_class

    def __contains__(self, name):
        return name in self._generators

    def __getitem__(self, key):
        return self._generators[key]

    def _new_generator(self, generator_name, scoped_output):
        if generator_name not in self._new_generators:
            return
        if generator_name in self._generators:  # Avoid colisions with user custom generators
            msg = ("******* Your custom generator name '{}' is colliding with a new experimental "
                   "built-in one. It is recommended to rename it. *******".format(generator_name))
            scoped_output.warning(msg)
            return
        if generator_name == "CMakeToolchain":
            from conan.tools.cmake import CMakeToolchain
            return CMakeToolchain
        elif generator_name == "CMakeDeps":
            from conan.tools.cmake import CMakeDeps
            return CMakeDeps
        elif generator_name == "AutotoolsDeps":
            from conan.tools.gnu import AutotoolsDeps
            return AutotoolsDeps
        elif generator_name == "AutotoolsToolchain":
            from conan.tools.gnu import AutotoolsToolchain
            return AutotoolsToolchain
        elif generator_name == "PkgConfigDeps":
            from conan.tools.gnu import PkgConfigDeps
            return PkgConfigDeps
        elif generator_name == "MSBuildToolchain":
            from conan.tools.microsoft import MSBuildToolchain
            return MSBuildToolchain
        elif generator_name == "MesonToolchain":
            from conan.tools.meson import MesonToolchain
            return MesonToolchain
        elif generator_name == "MSBuildDeps":
            from conan.tools.microsoft import MSBuildDeps
            return MSBuildDeps
        elif generator_name == "VCVars":
            from conan.tools.microsoft import VCVars
            return VCVars
        elif generator_name == "QbsToolchain" or generator_name == "QbsProfile":
            from conan.tools.qbs.qbsprofile import QbsProfile
            return QbsProfile
        elif generator_name == "VirtualBuildEnv":
            from conan.tools.env.virtualbuildenv import VirtualBuildEnv
            return VirtualBuildEnv
        elif generator_name == "VirtualRunEnv":
            from conan.tools.env.virtualrunenv import VirtualRunEnv
            return VirtualRunEnv
        elif generator_name == "BazelDeps":
            from conan.tools.google import BazelDeps
            return BazelDeps
        elif generator_name == "BazelToolchain":
            from conan.tools.google import BazelToolchain
            return BazelToolchain
        else:
            raise ConanException("Internal Conan error: Generator '{}' "
                                 "not commplete".format(generator_name))

    def write_generators(self, conanfile, old_gen_folder, new_gen_folder):
        """ produces auxiliary files, required to build a project or a package.
        """
        _receive_conf(conanfile)

        for generator_name in set(conanfile.generators):
            generator_class = self._new_generator(generator_name, conanfile.output)
            if generator_class:
                try:
                    generator = generator_class(conanfile)
                    conanfile.output.highlight("Generator '{}' calling "
                                               "'generate()'".format(generator_name))
                    mkdir(new_gen_folder)
                    with chdir(new_gen_folder):
                        generator.generate()
                    continue
                except Exception as e:
                    raise ConanException("Error in generator '{}': {}".format(generator_name,
                                                                              str(e)))

            try:
                generator_class = self._generators[generator_name]
            except KeyError:
                available = list(self._generators.keys()) + self._new_generators
                raise ConanException("Invalid generator '%s'. Available types: %s" %
                                     (generator_name, ", ".join(available)))
            generator = generator_class(conanfile)

            try:
                generator.output_path = old_gen_folder
                content = generator.content
                if isinstance(content, dict):
                    if generator.filename:
                        conanfile.output.warning("Generator %s is multifile. Property 'filename' "
                                                 "not used" % (generator_name,))
                    for k, v in content.items():
                        if generator.normalize:  # To not break existing behavior, to be removed 2.0
                            v = normalize(v)
                        conanfile.output.info("Generator %s created %s" % (generator_name, k))
                        save(join(old_gen_folder, k), v, only_if_modified=True)
                else:
                    content = normalize(content)
                    conanfile.output.info("Generator %s created %s" % (generator_name,
                                                                       generator.filename))
                    save(join(old_gen_folder, generator.filename), content, only_if_modified=True)
            except Exception as e:
                if get_env("CONAN_VERBOSE_TRACEBACK", False):
                    conanfile.output.error(traceback.format_exc())
                conanfile.output.error("Generator %s(file:%s) failed\n%s"
                             % (generator_name, generator.filename, str(e)))
                raise ConanException(e)


def _receive_conf(conanfile):
    """  collect conf_info from the immediate build_requires, aggregate it and injects/update
    current conf
    """
    # TODO: Open question 1: Only build_requires can define config?
    # TODO: Only direct build_requires?
    # TODO: Is really the best mechanism to define this info? Better than env-vars?
    # Conf only for first level build_requires
    for build_require in conanfile.dependencies.direct_build.values():
        if build_require.conf_info:
            conanfile.conf.compose(build_require.conf_info)


def write_toolchain(conanfile):

    if hasattr(conanfile, "generate"):
        conanfile.output.highlight("Calling generate()")
        mkdir(conanfile.generators_folder)
        with chdir(conanfile.generators_folder):
            with conanfile_exception_formatter(str(conanfile), "generate"):
                conanfile.generate()

    if conanfile.virtualbuildenv or conanfile.virtualrunenv:
        mkdir(conanfile.generators_folder)
        with chdir(conanfile.generators_folder):
            if conanfile.virtualbuildenv:
                from conan.tools.env.virtualbuildenv import VirtualBuildEnv
                env = VirtualBuildEnv(conanfile)
                env.generate()
            if conanfile.virtualrunenv:
                from conan.tools.env import VirtualRunEnv
                env = VirtualRunEnv(conanfile)
                env.generate()

    conanfile.output.highlight("Aggregating env generators")
    _generate_aggregated_env(conanfile)


def _generate_aggregated_env(conanfile):
    from conan.tools.microsoft import unix_path

    for group, env_scripts in conanfile.env_scripts.items():
        bats = []
        shs = []
        for env_script in env_scripts:
            path = os.path.join(conanfile.generators_folder, env_script)
            if env_script.endswith(".bat"):
                bats.append(path)
            elif env_script.endswith(".sh"):
                shs.append(unix_path(conanfile, path))
        if shs:
            sh_content = ". " + " && . ".join('"{}"'.format(s) for s in shs)
            save(os.path.join(conanfile.generators_folder, "conan{}.sh".format(group)), sh_content)
        if bats:
            lines = "\r\n".join('call "{}"'.format(b) for b in bats)
            bat_content = textwrap.dedent("""\
                            @echo off
                            {}
                            """.format(lines))
            save(os.path.join(conanfile.generators_folder, "conan{}.bat".format(group)), bat_content)
