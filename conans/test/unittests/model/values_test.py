import unittest

from conans.model.values import Values


class ValuesTest(unittest.TestCase):

    def test_simple(self):
        v = Values()
        self.assertEqual(v.compiler, None)
        v.compiler = 3
        self.assertTrue(v.compiler == "3")

        self.assertEqual(v.compiler.version, None)
        v.compiler.version = "asfaf"
        self.assertEqual(v.compiler.version, "asfaf")

        my_list = v.as_list()
        self.assertEqual(my_list, [('compiler', '3'),
                                   ('compiler.version', 'asfaf')])

        values = Values.from_list(my_list)
        self.assertEqual(values.dumps(), v.dumps())

        v.compiler = None
        self.assertEqual(v.as_list(), [('compiler', 'None')])
        self.assertEqual(v.dumps(), "compiler=None")
