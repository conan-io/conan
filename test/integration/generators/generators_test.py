from conan.test.utils.tools import TestClient


class TestGenerators:

    def test_error(self):
        client = TestClient()
        client.save({"conanfile.txt": "[generators]\nunknown"})
        client.run("install . --build=*", assert_error=True)
        assert "ERROR: Invalid generator 'unknown'. Available types:" in client.out
