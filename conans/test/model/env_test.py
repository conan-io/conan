import unittest
from conans.model.env_info import DepsEnvInfo
from conans.model.ref import ConanFileReference


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
