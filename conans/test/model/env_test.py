import unittest
from conans.model.env_info import DepsEnvInfo, EnvValues, EnvInfo
from conans.model.ref import ConanFileReference


class EnvValuesTest(unittest.TestCase):

    def test_model(self):
        env = EnvValues()
        env.add("Z", "1")
        self.assertEquals(env.env_dicts(""), ({"Z": "1"}, {}))
        env.add("Z", "2")
        self.assertEquals(env.env_dicts(""), ({"Z": "1"}, {}))
        env.add("B", "223")
        self.assertEquals(env.env_dicts(""), ({"Z": "1", "B": "223"}, {}))
        env.add("B", "224", "package1")
        self.assertEquals(env.env_dicts(""), ({"Z": "1", "B": "223"}, {}))
        self.assertEquals(env.env_dicts("package1"), ({"Z": "1", "B": "224"}, {}))
        env.add("A", "1", "package1")
        self.assertEquals(env.env_dicts("package1"), ({"Z": "1", "B": "224", "A": "1"}, {}))
        self.assertEquals(env.env_dicts(""), ({"Z": "1", "B": "223"}, {}))
        env.add("J", "21", "package21")
        self.assertEquals(env.env_dicts(""), ({"Z": "1", "B": "223"}, {}))
        self.assertEquals(env.env_dicts("package1"), ({"Z": "1", "B": "224", "A": "1"}, {}))
        env.add("A", ["99"], "package1")
        self.assertEquals(env.env_dicts("package1"), ({"Z": "1", "B": "224", "A": "1"}, {}))
        env.add("M", ["99"], "package1")
        self.assertEquals(env.env_dicts("package1"), ({"Z": "1", "B": "224", "A": "1"}, {"M": ["99"]}))
        env.add("M", "100", "package1")
        self.assertEquals(env.env_dicts("package1"), ({"Z": "1", "B": "224", "A": "1"}, {"M": ["99", "100"]}))

        self.assertEquals(env.env_dicts(""), ({"Z": "1", "B": "223"}, {}))

    def test_update_concat(self):
        env_info = EnvInfo()
        env_info.path.append("SOME/PATH")
        deps_info = DepsEnvInfo()
        deps_info.update(env_info, "lib")

        deps_info2 = DepsEnvInfo()
        deps_info2.update(env_info, "lib2")

        env = EnvValues()
        env.add("PATH", ["MYPATH"])
        env.update(deps_info)

        self.assertEquals(env.env_dicts(None), ({}, {'PATH': ['MYPATH', 'SOME/PATH']}))

        env.update(deps_info2)

        self.assertEquals(env.env_dicts(None), ({}, {'PATH': ['MYPATH', 'SOME/PATH', 'SOME/PATH']}))

    def update_priority_test(self):

        env = EnvValues()
        env.add("VAR", "VALUE1")

        env2 = EnvValues()
        env2.add("VAR", "VALUE2")

        env.update(env2)

        # Already set by env, discarded new value
        self.assertEquals(env.env_dicts(None),  ({'VAR': 'VALUE1'}, {}))

        # Updates with lists and values
        env = EnvValues()
        env.add("VAR", ["1"])
        env.add("VAR", "2")
        self.assertEquals(env.env_dicts(None), ({}, {'VAR': ['1', '2']}))

        # If the first value is not a list won't append
        env = EnvValues()
        env.add("VAR", "1")
        env.add("VAR", ["2"])
        self.assertEquals(env.env_dicts(None), ({'VAR': '1'}, {}))


class EnvInfoTest(unittest.TestCase):

    def assign_test(self):
        env = DepsEnvInfo()
        env.foo = ["var"]
        env.foo.append("var2")
        env.foo2 = "var3"
        env.foo2 = "var4"
        env.foo63 = "other"

        self.assertEquals(env.vars, {"foo": ["var", "var2"], "foo2": "var4", "foo63": "other"})

    def update_test(self):
        env = DepsEnvInfo()
        env.foo = ["var"]
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
