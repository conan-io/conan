import unittest
from conans.client.output import ConanOutput
from io import StringIO


class OutputTest(unittest.TestCase):

    def simple_output_test(self):
        stream = StringIO()
        output = ConanOutput(stream)
        output.rewrite_line("This is a very long line that has to be truncated somewhere, "
                            "because it is so long it doesn't fit in the output terminal")
        self.assertIn("This is a very long line that ha ... esn't fit in the output terminal",
                      stream.getvalue())
