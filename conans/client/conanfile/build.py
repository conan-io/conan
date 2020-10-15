import os

from conans.client.tools.env import environment_append, no_op
from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.util.log import logger


def run_build_method(conanfile, hook_manager, config, **hook_kwargs):
    hook_manager.execute("pre_build", conanfile=conanfile, **hook_kwargs)

    logger.debug("Call conanfile.build() with files in build folder: %s",
                 os.listdir(conanfile.build_folder))

    shims_path = os.path.join(conanfile.install_folder, '.shims')  # TODO: This is a convention, write it somewhere else
    with environment_append({'PATH': [shims_path, ]}) if config.shims_enabled else no_op():
        with get_env_context_manager(conanfile):
            conanfile.output.highlight("Calling build()")
            with conanfile_exception_formatter(str(conanfile), "build"):
                conanfile.build()

    hook_manager.execute("post_build", conanfile=conanfile, **hook_kwargs)
