from conan.test.utils.tools import TestClient, GenConanfile
import textwrap
import json
import re

c = TestClient(light=True)
profile = textwrap.dedent("""\
    [settings]
    os=Linux
    [tool_requires]
    !tool1*|tool2*: myextratool/1.0
    """)
c.save({
    "tool1/conanfile.py": GenConanfile("tool1", "1.0"),
    "other/conanfile.py": GenConanfile("other", "1.0"),
    "myextratool/conanfile.py": GenConanfile("myextratool", "1.0"),
    "profile.txt": profile,
})
c.run("export tool1 --name=tool1 --version=1.0")
c.run("export other --name=other --version=1.0")
c.run("export myextratool --name=myextratool --version=1.0")
c.run(
    "graph info --requires=other/1.0 --package-filter=other* "
    "-pr:b=profile.txt --build=* --format=json"
)
out = c.out
m = re.search(r'\{\s*"graph"', out)
data = json.loads(out[m.start() :])
for n in data["graph"]["nodes"].values():
    print(n.get("ref"), "->", n.get("build_requires"))
