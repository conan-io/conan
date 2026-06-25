import textwrap

from conan.test.utils.tools import TestClient


class TestInit:
    def test_wrong_init(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                def init(self):
                    random_error
            """)

        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        assert "Error in init() method, line 5" in client.out
        assert "name 'random_error' is not defined" in client.out

    def test_init(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            import os
            import json
            class Lib(ConanFile):
                exports = "data.json"
                def init(self):
                    data = load(self, os.path.join(self.recipe_folder, "data.json"))
                    d = json.loads(data)
                    self.license = d["license"]
                    self.description = d["description"]
                def export(self):
                    self.output.info("description: %s" % self.description)
                    self.output.info("license: %s" % self.license)
                def build(self):
                    self.output.info("description: %s" % self.description)
                    self.output.info("license: %s" % self.license)
            """)
        data = '{"license": "MIT", "description": "MyDescription"}'
        client.save({"conanfile.py": conanfile,
                     "data.json": data})

        client.run("export . --name=pkg --version=version")
        assert "description: MyDescription" in client.out
        assert "license: MIT" in client.out
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        assert "description: MyDescription" in client.out
        assert "license: MIT" in client.out

    def test_options_from_yml(self):
        client = TestClient()
        conanfile = textwrap.dedent("""\
            from conan import ConanFile

            class Lib(ConanFile):
                name = "pkg"
                version = "0.1"

                def init(self):
                    self.options.update(self.conan_data["options"],
                                        self.conan_data["default_options"])
            """)
        conandata = textwrap.dedent("""\
            options:
                myopt1: [1, 2, 3]
                myopt2: [null, potato]
                myopt3: [null, ANY]
            default_options:
                myopt1: 2
            """)
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": conandata})

        client.run("create . ")
        client.run("create . -o &:myopt1=1 -o &:myopt2=potato -o &:myopt3=whatever")
        client.run("list *:*")

        assert "myopt1: 2" in client.out
        assert "myopt1: 1" in client.out
        assert "myopt2: potato" in client.out
        assert "myopt3: whatever" in client.out
