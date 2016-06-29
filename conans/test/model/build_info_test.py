import unittest
from conans.model.build_info import DepsCppInfo
from conans.client.generators import TXTGenerator
from collections import namedtuple


class BuildInfoTest(unittest.TestCase):

    def _equal(self, item1, item2):
        for field in item1.fields:
            self.assertEqual(getattr(item1, field),
                             getattr(item2, field))

    def help_test(self):
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.includedirs.append("C:/whatever")
        deps_cpp_info.includedirs.append("C:/whenever")
        deps_cpp_info.libdirs.append("C:/other")
        deps_cpp_info.libs.extend(["math", "winsock", "boost"])
        child = DepsCppInfo()
        child.includedirs.append("F:/ChildrenPath")
        child.cppflags.append("cxxmyflag")
        deps_cpp_info._dependencies["Boost"] = child
        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None)).content
        deps_cpp_info2 = DepsCppInfo.loads(output)
        self._equal(deps_cpp_info, deps_cpp_info2)
