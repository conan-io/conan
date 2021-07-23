import os

from conans.client.tools import no_op
from conans.errors import conanfile_exception_formatter
from conans.util.log import logger


def run_build_method(conanfile, hook_manager, **hook_kwargs):
    hook_manager.execute("pre_build", conanfile=conanfile, **hook_kwargs)

    logger.debug("Call conanfile.build() with files in build folder: %s",
                 os.listdir(conanfile.build_folder))
    with no_op():  # TODO: Remove this in a later refactor
        conanfile.output.highlight("Calling build()")
        with conanfile_exception_formatter(str(conanfile), "build"):
            conanfile.build()

    hook_manager.execute("post_build", conanfile=conanfile, **hook_kwargs)
