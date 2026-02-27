import sys
from unittest import mock

import pytest

from conan.api.output import ConanOutput, init_colorama
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.tools import redirect_output


class TestConanOutput:

    @pytest.mark.parametrize("isatty, env", [(True, {"NO_COLOR": "1"}),
                                             (True, {"NO_COLOR": "0"})])
    def test_output_color_prevent_strip(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is False
                init.assert_not_called()


@pytest.mark.parametrize("force", ["1", "0", "foo"])
def test_output_forced(force):
    env = {"CLICOLOR_FORCE": force}
    forced = force != "0"
    with mock.patch("colorama.init") as init:
        with mock.patch("sys.stderr.isatty", return_value=False), \
             mock.patch.dict("os.environ", env, clear=True):
            init_colorama(sys.stderr)
            out = ConanOutput()

            assert out.color is forced
            if not forced:
                init.assert_not_called()


def test_output_chainable():
    stderr = RedirectedTestOutput()
    with redirect_output(stderr):
        ConanOutput(scope="My package")\
            .title("My title")\
            .highlight("Worked")\
            .info("But there was more that needed to be said")
    assert "My package" in stderr.getvalue()
    assert "My title" in stderr.getvalue()
    assert "Worked" in stderr.getvalue()
    assert "But there was more that needed to be said" in stderr.getvalue()
