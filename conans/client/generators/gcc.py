from conans.client.generators.compiler_args import CompilerArgsGenerator
from conans.paths import BUILD_INFO_GCC


class GCCGenerator(CompilerArgsGenerator):
    """Backwards compatibility with 'gcc' generator, there the compiler was fixed to gcc always"""
    @property
    def filename(self):
        return BUILD_INFO_GCC

    @property
    def compiler(self):
        return "gcc"
