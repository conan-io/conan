# -*- coding: utf-8 -*-

from conan.tools.misc.makedeps import MakeDeps

class ShDeps(MakeDeps):

    _output_filename = "conandeps.sh"
    _title = "Shell variables from Conan dependencies"

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        super().__init__(conanfile)

    def _var_ref(self, var):
        return f"${{{var}}}"

    def _var_assign_single(self, var, value):
        return f"{var}=\"{value}\""

    def _var_assign_multi(self, var, value):
        return f"{var}=\"" + " ".join(value) + "\""
