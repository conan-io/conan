from conans.client.toolchain.cmake import CMakeToolchain
from conans.errors import conanfile_exception_formatter, ConanException


def write_toolchain(conanfile, path, output):
    if hasattr(conanfile, "toolchain"):
        if callable(conanfile.toolchain):
            # This is the toolchain
            with conanfile_exception_formatter(str(conanfile), "toolchain"):
                tc = conanfile.toolchain()
        else:
            try:
                toolchain = {"cmake": CMakeToolchain}[conanfile.toolchain]
            except KeyError:
                raise ConanException("Unknown toolchain '%s'" % conanfile.toolchain)
            tc = toolchain(conanfile)
        output.highlight("Generating toolchain files")
        tc.dump(path)

        # TODO: Lets discuss what to do with the environment
