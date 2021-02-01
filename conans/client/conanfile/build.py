import os

from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.util.log import logger


def run_build_method(conanfile, hook_manager, **hook_kwargs):
    hook_manager.execute("pre_build", conanfile=conanfile, **hook_kwargs)

    logger.debug("Call conanfile.build() with files in build folder: %s",
                 os.listdir(conanfile.build_folder))
    with get_env_context_manager(conanfile):
        conanfile.output.highlight("Calling build()")
        with conanfile_exception_formatter(str(conanfile), "build"):
            conanfile.build()

    hook_manager.execute("post_build", conanfile=conanfile, **hook_kwargs)
