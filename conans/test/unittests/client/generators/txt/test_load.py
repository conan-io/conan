import textwrap
import unittest

from conans.client.generators.text import TXTGenerator


class LoadContentTestCase(unittest.TestCase):

    def test_load_sytem_libs(self):
        # Loading an item that contains an underscore
        content = textwrap.dedent("""
            [system_libs]
            a-real-flow-contains-aggregated-list-here

            [name_requirement]
            requirement_name

            [rootpath_requirement]
            requirement_rootpath

            [system_libs_requirement]
            requirement

            [name_requirement_other]
            requirement_other_name

            [rootpath_requirement_other]
            requirement_other_rootpath

            [system_libs_requirement_other]
            requirement_other
        """)

        deps_cpp_info, _, _, _ = TXTGenerator.loads(content)
        self.assertListEqual(list(deps_cpp_info.system_libs), ["requirement", "requirement_other"])
        self.assertListEqual(list(deps_cpp_info["requirement"].system_libs), ["requirement", ])
        self.assertListEqual(list(deps_cpp_info["requirement_other"].system_libs),
                             ["requirement_other", ])
