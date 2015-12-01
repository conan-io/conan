import unittest
from conans.model.build_info import DepsCppInfo


class BuildInfoTest(unittest.TestCase):

    def _equal(self, item1, item2):
        for field in item1.fields:
            self.assertEqual(getattr(item1, field),
                             getattr(item2, field))

    def help_test(self):
        imports = DepsCppInfo()
        imports.includedirs.append("C:/whatever")
        imports.includedirs.append("C:/whenever")
        imports.libdirs.append("C:/other")
        imports.libs.extend(["math", "winsock", "boost"])
        child = DepsCppInfo()
        child.includedirs.append("F:/ChildrenPath")
        child.cppflags.append("cxxmyflag")
        imports._dependencies["Boost"] = child
        output = repr(imports)
        imports2 = DepsCppInfo.loads(output)
        self._equal(imports, imports2)
