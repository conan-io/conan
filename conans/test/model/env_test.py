import unittest
from conans.model.env import DepsEnvInfo, EnvValues, EnvInfo
from conans.model.ref import ConanFileReference


class EnvValuesTest(unittest.TestCase):

    def test_model(self):
        env = EnvValues()
        env.add("Z", "1")
        self.assertEquals(env.all_package_values(), [])
        self.assertEquals(env.global_values(), [("Z", "1")])
        env.add("Z", "2")
        self.assertEquals(env.global_values(), [("Z", "1")])
        env.add("B", "223")
        self.assertEquals(env.global_values(), [("B", "223"), ("Z", "1")])
        env.add("B", "224", "package1")
        self.assertEquals(env.global_values(), [("B", "223"), ("Z", "1")])
        self.assertEquals(env.package_values("package1"), [("B", "224")])
        env.add("A", "1", "package1")
        self.assertEquals(env.package_values("package1"), [("A", "1"), ("B", "224")])
        self.assertEquals(env.all_package_values(), [('package1:A', '1'), ('package1:B', '224')])
        env.add("J", "21", "package21")
        self.assertEquals(env.all_package_values(), [('package1:A', '1'),
                                                     ('package1:B', '224'), ('package21:J', '21')])

        self.assertEquals(env.global_values(), [("B", "223"), ("Z", "1")])

    def test_update_concat(self):
        env_info = EnvInfo()
        env_info.path.append("SOME/PATH")
        deps_info = DepsEnvInfo()
        deps_info.update(env_info, ConanFileReference.loads("lib/1.0@lasote/stable"))

        deps_info2 = DepsEnvInfo()
        deps_info2.update(env_info, ConanFileReference.loads("lib2/1.0@lasote/stable"))

        env = EnvValues()
        env.add("PATH", "MYPATH")
        env.update(deps_info)

        self.assertEquals(env.env_dict(None), {'PATH': 'MYPATH:SOME/PATH'})

        env.update(deps_info2)

        self.assertEquals(env.env_dict(None), {'PATH': 'MYPATH:SOME/PATH:SOME/PATH'})

    def update_priority_test(self):

        env = EnvValues()
        env.add("VAR", "VALUE1")

        env2 = EnvValues()
        env2.add("VAR", "VALUE2")

        env.update(env2)

        # Already set by env, discarded new value
        self.assertEquals(env.env_dict(None), {'VAR': 'VALUE1'})


class EnvInfoTest(unittest.TestCase):

    def assign_test(self):
        env = DepsEnvInfo()
        env.foo = "var"
        env.foo.append("var2")
        env.foo2 = "var3"
        env.foo2 = "var4"
        env.foo63 = "other"

        self.assertEquals(env.vars, {"foo": ["var", "var2"], "foo2": "var4", "foo63": "other"})

    def update_test(self):
        env = DepsEnvInfo()
        env.foo = "var"
        env.foo.append("var2")
        env.foo2 = "var3"
        env.foo2 = "var4"
        env.foo63 = "other"

        env2 = DepsEnvInfo()
        env2.foo = "new_value"
        env2.foo2.append("not")
        env2.foo3.append("var3")

        env.update(env2, ConanFileReference.loads("pack/1.0@lasote/testing"))

        self.assertEquals(env.vars, {"foo": ["var", "var2", "new_value"],
                                     "foo2": "var4", "foo3": ["var3"],
                                     "foo63": "other"})
