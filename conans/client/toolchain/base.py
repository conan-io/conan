from conans.client.toolchain.cmake import CMakeToolchain
from conans.client.tools import chdir
from conans.errors import conanfile_exception_formatter, ConanException


def write_toolchain(conanfile, path, output):
    if hasattr(conanfile, "toolchain"):
        if callable(conanfile.toolchain):
            # This is the toolchain
            with chdir(path):
                with conanfile_exception_formatter(str(conanfile), "toolchain"):
                    tc = conanfile.toolchain()
        else:
            try:
                toolchain = {"cmake": CMakeToolchain}[conanfile.toolchain]
            except KeyError:
                raise ConanException("Unknown toolchain '%s'" % conanfile.toolchain)
            tc = toolchain(conanfile)
        output.highlight("Generating toolchain files")
        if tc is not None:  # Allow the toolchain method to not return
            tc.create_toolchain_files(path)

        # TODO: Lets discuss what to do with the environment
