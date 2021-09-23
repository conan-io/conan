import os
import textwrap

from conans.errors import ConanException, conanfile_exception_formatter
from conans.util.files import save, mkdir
from ..tools import chdir

_generators = ["CMakeToolchain", "CMakeDeps", "MSBuildToolchain",
               "MesonToolchain", "MSBuildDeps", "QbsToolchain", "msbuild",
               "VirtualRunEnv", "VirtualBuildEnv", "AutotoolsDeps",
               "AutotoolsToolchain", "BazelDeps", "BazelToolchain", "PkgConfigDeps",
               "VCVars", "deploy"]


def _get_generator_class(generator_name):
    if generator_name not in _generators:
        raise ConanException("Invalid generator '%s'. Available types: %s" %
                             (generator_name, ", ".join(_generators)))
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
    elif generator_name == "deploy":
        from conans.client.generators.deploy import DeployGenerator
        return DeployGenerator
    else:
        raise ConanException("Internal Conan error: Generator '{}' "
                             "not complete".format(generator_name))


def write_generators(conanfile, output):
    new_gen_folder = conanfile.generators_folder
    _receive_conf(conanfile)

    for generator_name in set(conanfile.generators):
        generator_class = _get_generator_class(generator_name)
        if generator_class:
            try:
                generator = generator_class(conanfile)
                output.highlight("Generator '{}' calling 'generate()'".format(generator_name))
                mkdir(new_gen_folder)
                with chdir(new_gen_folder):
                    generator.generate()
                continue
            except Exception as e:
                raise ConanException("Error in generator '{}': {}".format(generator_name, str(e)))

    if hasattr(conanfile, "generate"):
        output.highlight("Calling generate()")
        mkdir(new_gen_folder)
        with chdir(new_gen_folder):
            with conanfile_exception_formatter(str(conanfile), "generate"):
                conanfile.generate()

    if conanfile.virtualbuildenv or conanfile.virtualrunenv:
        mkdir(new_gen_folder)
        with chdir(new_gen_folder):
            if conanfile.virtualbuildenv:
                from conan.tools.env.virtualbuildenv import VirtualBuildEnv
                env = VirtualBuildEnv(conanfile)
                env.generate()
            if conanfile.virtualrunenv:
                from conan.tools.env import VirtualRunEnv
                env = VirtualRunEnv(conanfile)
                env.generate()

    output.highlight("Aggregating env generators")
    _generate_aggregated_env(conanfile)


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
