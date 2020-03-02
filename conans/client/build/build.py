
from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager


def build_conanfile(conanfile, hook_manager, **hook_kwargs):
    hook_manager.execute("pre_build", **hook_kwargs)

    with get_env_context_manager(conanfile):
        conanfile.output.highlight("Running build()")
        with conanfile_exception_formatter(str(conanfile), "build"):
            conanfile.build()

    hook_manager.execute("post_build", **hook_kwargs)
