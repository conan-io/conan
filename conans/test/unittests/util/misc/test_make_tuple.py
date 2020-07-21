import unittest

from conans.util.misc import make_tuple


class MakeTupleTestCase(unittest.TestCase):
    def test_corner_cases(self):
        self.assertIsNone(make_tuple(None))
        self.assertTupleEqual(make_tuple("one"), ("one",))

    def test_iterable(self):
        self.assertTupleEqual(make_tuple([1, 2, 3]), (1, 2, 3))
        self.assertTupleEqual(make_tuple(("one", "two")), ("one", "two"))
        self.assertTupleEqual(make_tuple({1: "a", 2: "b", 3: "c"}.keys()), (1, 2, 3))
        self.assertTupleEqual(make_tuple({1: "a", 2: "b", 3: "c"}.values()), ("a", "b", "c"))

    def test_generator(self):
        def items():
            for i in [1, 2, 3]:
                yield i

        self.assertTupleEqual(make_tuple(items()), (1, 2, 3))
