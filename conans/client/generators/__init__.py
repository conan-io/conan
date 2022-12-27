import os
import traceback
import importlib

from conans.client.subsystems import deduce_subsystem, subsystem_path
from conans.errors import ConanException, conanfile_exception_formatter
from conans.util.files import save, mkdir, chdir

_generators = {"CMakeToolchain": "conan.tools.cmake", "CMakeDeps": "conan.tools.cmake",
               "MesonToolchain": "conan.tools.meson", "MesonDeps": "conan.tools.meson",
               "MSBuildDeps": "conan.tools.microsoft", "MSBuildToolchain": "conan.tools.microsoft",
               "NMakeToolchain": "conan.tools.microsoft", "NMakeDeps": "conan.tools.microsoft",
               "VCVars": "conan.tools.microsoft",
               "QbsProfile": "conan.tools.qbs.qbsprofile",
               "VirtualRunEnv": "conan.tools.env.virtualrunenv",
               "VirtualBuildEnv": "conan.tools.env.virtualbuildenv",
               "AutotoolsDeps": "conan.tools.gnu", "AutotoolsToolchain": "conan.tools.gnu",
               "PkgConfigDeps": "conan.tools.gnu",
               "BazelDeps": "conan.tools.google", "BazelToolchain": "conan.tools.google",
               "IntelCC": "conan.tools.intel",
               "XcodeDeps": "conan.tools.apple", "XcodeToolchain": "conan.tools.apple",
               "PremakeDeps": "conan.tools.premake",
               }


def _get_generator_class(generator_name):
    # QbsToolchain is an alias for QbsProfile
    if generator_name == "QbsToolchain":
        generator_name = "QbsProfile"

    try:
        generator_class = _generators[generator_name]
        # This is identical to import ... form ... in terms of cacheing
        return getattr(importlib.import_module(generator_class), generator_name)
    except KeyError as e:
        raise ConanException(f"Invalid generator '{generator_name}'. "
                             f"Available types: {', '.join(_generators)}") from e
    except ImportError as e:
        raise ConanException("Internal Conan error: "
                             f"Could not find module {generator_class}") from e
    except AttributeError as e:
        raise ConanException("Internal Conan error: "
                             f"Could not find name {generator_name} "
                             f"inside module {generator_class}") from e


def write_generators(conanfile, hook_manager):
    new_gen_folder = conanfile.generators_folder
    _receive_conf(conanfile)

    hook_manager.execute("pre_generate", conanfile=conanfile)

    if conanfile.generators:
        conanfile.output.info(f"Writing generators to {new_gen_folder}")
    # generators check that they are not present in the generators field,
    # to avoid duplicates between the generators attribute and the generate() method
    # They would raise an exception here if we don't invalidate the field while we call them
    old_generators = set(conanfile.generators)
    conanfile.generators = []
    try:
        for generator_name in old_generators:
            generator_class = _get_generator_class(generator_name)
            if generator_class:
                try:
                    generator = generator_class(conanfile)
                    conanfile.output.highlight(f"Generator '{generator_name}' calling 'generate()'")
                    mkdir(new_gen_folder)
                    with chdir(new_gen_folder):
                        generator.generate()
                    continue
                except Exception as e:
                    # When a generator fails, it is very useful to have the whole stacktrace
                    conanfile.output.error(traceback.format_exc())
                    raise ConanException(f"Error in generator '{generator_name}': {str(e)}") from e
    finally:
        # restore the generators attribute, so it can raise
        # if the user tries to instantiate a generator already present in generators
        conanfile.generators = old_generators
    if hasattr(conanfile, "generate"):
        conanfile.output.highlight("Calling generate()")
        mkdir(new_gen_folder)
        with chdir(new_gen_folder):
            with conanfile_exception_formatter(conanfile, "generate"):
                conanfile.generate()

    if conanfile.virtualbuildenv:
        mkdir(new_gen_folder)
        with chdir(new_gen_folder):
            from conan.tools.env.virtualbuildenv import VirtualBuildEnv
            env = VirtualBuildEnv(conanfile)
            env.generate()
    if conanfile.virtualrunenv:
        mkdir(new_gen_folder)
        with chdir(new_gen_folder):
            from conan.tools.env import VirtualRunEnv
            env = VirtualRunEnv(conanfile)
            env.generate()

    conanfile.output.highlight("Aggregating env generators")
    _generate_aggregated_env(conanfile)

    hook_manager.execute("post_generate", conanfile=conanfile)


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
            conanfile.conf.compose_conf(build_require.conf_info)


def _generate_aggregated_env(conanfile):

    def deactivates(filenames):
        # FIXME: Probably the order needs to be reversed
        result = []
        for s in filenames:
            folder, f = os.path.split(s)
            result.append(os.path.join(folder, "deactivate_{}".format(f)))
        return result

    for group, env_scripts in conanfile.env_scripts.items():
        subsystem = deduce_subsystem(conanfile, group)
        bats = []
        shs = []
        ps1s = []
        for env_script in env_scripts:
            path = os.path.join(conanfile.generators_folder, env_script)
            if env_script.endswith(".bat"):
                bats.append(path)
            elif env_script.endswith(".sh"):
                shs.append(subsystem_path(subsystem, path))
            elif env_script.endswith(".ps1"):
                ps1s.append(path)
        if shs:
            def sh_content(files):
                return ". " + " && . ".join('"{}"'.format(s) for s in files)
            filename = "conan{}.sh".format(group)
            save(os.path.join(conanfile.generators_folder, filename), sh_content(shs))
            save(os.path.join(conanfile.generators_folder, "deactivate_{}".format(filename)),
                 sh_content(deactivates(shs)))
        if bats:
            def bat_content(files):
                return "\r\n".join(["@echo off"] + ['call "{}"'.format(b) for b in files])
            filename = "conan{}.bat".format(group)
            save(os.path.join(conanfile.generators_folder, filename), bat_content(bats))
            save(os.path.join(conanfile.generators_folder, "deactivate_{}".format(filename)),
                 bat_content(deactivates(bats)))
        if ps1s:
            def ps1_content(files):
                return "\r\n".join(['& "{}"'.format(b) for b in files])
            filename = "conan{}.ps1".format(group)
            save(os.path.join(conanfile.generators_folder, filename), ps1_content(ps1s))
            save(os.path.join(conanfile.generators_folder, "deactivate_{}".format(filename)),
                 ps1_content(deactivates(ps1s)))
