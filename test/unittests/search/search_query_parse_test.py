import unittest

from conan.internal.api.list.query_parse import _evaluate_postfix, _infix_to_postfix


class QueryParseTest(unittest.TestCase):

    def test_get_postfix(self):
        r = _infix_to_postfix("")
        self.assertEqual(r, [])

        r = _infix_to_postfix("a=2")
        self.assertEqual(r, ["a=2"])

        r = _infix_to_postfix("a=2 OR b=3")
        self.assertEqual(r, ["a=2", "b=3", "|"])

        r = _infix_to_postfix("a= OR b=")
        self.assertEqual(r, ["a=", "b=", "|"])  # Equivalent to ""

        r = _infix_to_postfix("(a=2 OR b=3) AND (j=34 AND j=45) OR (a=1)")
        self.assertEqual(r, ["a=2", "b=3", "|", "j=34", "j=45", "&", "a=1", "&", "|"])

        with self.assertRaisesRegex(Exception, "Invalid expression: 2"):
            r = _infix_to_postfix("a= 2 OR b=3")

    def test_evaluate_postfix(self):

        def evaluator(expr):
            return expr in ("a=2", "j=45")

        def evaluate(q):
            r = _infix_to_postfix(q)
            return _evaluate_postfix(r, evaluator)

        self.assertTrue(evaluate("a=2"))
        self.assertFalse(evaluate("a=4"))
        self.assertTrue(evaluate("a=2 OR a=3"))
        self.assertTrue(evaluate("a=4 OR j=45"))
        self.assertFalse(evaluate("a=4 AND j=45"))
        self.assertTrue(evaluate("a=2 AND (f=23 OR j=45)"))
        self.assertFalse(evaluate("a=2 AND (f=23 OR j=435)"))
        self.assertTrue(evaluate("a=2 AND j=45 OR h=23"))
        self.assertTrue(evaluate("a=2 AND j=45 OR (h=23 AND a=2)"))
        self.assertTrue(evaluate("((((a=2 AND ((((f=23 OR j=45))))))))"))
        self.assertFalse(evaluate("((((a=2 AND ((((f=23 OR j=42))))))))"))
