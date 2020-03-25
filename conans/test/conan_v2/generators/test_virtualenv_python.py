from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class VirtualenvPythonTestCase(ConanV2ModeTestCase):

    def test_deprecate_virtualenv_python(self):
        t = self.get_client()
        t.run("new name/version@user/channel -b")
        t.run("create . name/version@user/channel")
        t.run("install name/version@user/channel -g virtualenv_python", assert_error=True)
        self.assertIn("ERROR: Conan v2 incompatible: 'virtualenv_python' generator is deprecated",
                      t.out)
