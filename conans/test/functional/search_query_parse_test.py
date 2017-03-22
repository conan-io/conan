import unittest
from conans.search.query_parse import infix_to_postfix, evaluate_postfix


class QueryParseTest(unittest.TestCase):

    def test_get_postfix(self):
        r = infix_to_postfix("")
        self.assertEquals(r, [])

        r = infix_to_postfix("a=2")
        self.assertEquals(r, ["a=2"])

        r = infix_to_postfix("a=2 OR b=3")
        self.assertEquals(r, ["a=2", "b=3", "|"])

        r = infix_to_postfix("a= OR b=")
        self.assertEquals(r, ["a=", "b=", "|"])  # Equivalent to ""

        r = infix_to_postfix("(a=2 OR b=3) AND (j=34 AND j=45) OR (a=1)")
        self.assertEquals(r, ["a=2", "b=3", "|", "j=34", "j=45", "&", "a=1", "&", "|"])

        with self.assertRaisesRegexp(Exception, "Invalid expression: 2"):
            r = infix_to_postfix("a= 2 OR b=3")

    def test_evaluate_postfix(self):

        def evaluator(expr):
            return expr in ("a=2", "j=45")

        def evaluate(q):
            r = infix_to_postfix(q)
            return evaluate_postfix(r, evaluator)

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
