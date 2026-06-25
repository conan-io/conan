import textwrap
import time

import pytest

from conan.test.utils.tools import TestClient, GenConanfile

RUN_COUNT = 2


@pytest.mark.skip(reason="Compatibility performance test")
class TestCompatibilityPerformance:

    results = []

    @pytest.fixture(scope="module", autouse=True)
    def timings(self):
        results = []
        yield results

        import matplotlib.pyplot as plt

        fig = plt.figure()
        ax = fig.add_subplot()

        ax.set_title("Compatibility performance in real Artifactory server (last match, unoptimized)")

        #ax_tot = ax.twinx()

        # Plot a basic wireframe.

        grouping = {}
        x, y, y_tot_opt, y_tot_non = [], [], [], []
        stderr_opt, stderr_non = [], []
        for factors, run, with_optimization, duration in results:
            group = grouping.setdefault(factors, {"opt": [], "non": []})
            if with_optimization:
                group["opt"].append(duration)
            else:
                group["non"].append(duration)

        def ssd(values, mean):
            return sum((v - mean) ** 2 for v in values) / (len(values) - 1)

        for factors, durations in sorted(grouping.items()):
            x.append(factors)
            y.append(0)

            mean_opt = sum(durations["opt"]) / RUN_COUNT
            mean_non = sum(durations["non"]) / RUN_COUNT
            y_tot_opt.append(mean_opt)
            y_tot_non.append(mean_non)

            # ssd_opt = ssd(durations["opt"], mean_opt)
            # ssd_non = ssd(durations["non"], mean_non)
            # stderr_opt.append(ssd_opt / (RUN_COUNT ** 0.5))
            # stderr_non.append(ssd_non / (RUN_COUNT ** 0.5))

        max_diff_y = max(y)
        min_diff_y = min(min(y), 0)
        # ax_tot.set_ylim(ymin=min_diff_y-0.1*min_diff_y, ymax=max_diff_y+0.1*max_diff_y)

        max_tot_y = max(max(y_tot_non), max(y_tot_opt))
        ax.set_ylim(ymin=0, ymax=max_tot_y+0.1*max_tot_y)

        ax.grid(visible=True, which="major", axis="y", linestyle="--")
        # ax_tot.set_xticks(x)

        ax.set_xticks(x)
        ax.plot(x, y_tot_non, 'red', marker='x', label="Without optimization", linestyle=":")
        # ax.errorbar(x, y_tot_non, yerr=stderr_non)
        ax.plot(x, y_tot_opt, 'blue', marker='x', label="With optimization", linestyle=":")
        # ax.errorbar(x, y_tot_opt, yerr=stderr_opt)

        # ax_tot.plot(x, y, 'gray', marker='o', linestyle="--", label="Difference total")
        # ax_tot.set_ylabel("Total time diff (s)")

        ax.set_xlabel("Number of compatible configurations in server")
        ax.set_ylabel("Total time (s)")
        ax.legend(loc="upper left")

        # ax_tot.legend(loc="upper right")

        plt.show()

    @pytest.mark.parametrize("runs", range(RUN_COUNT))
    @pytest.mark.parametrize("with_optimization", [True, False])
    @pytest.mark.parametrize("factors", [pow(2, n) for n in range(1, 6)])
    def test_list_only_compatibility(self, timings, with_optimization, factors, runs):
        tc = TestClient(light=True)
        tc.run("remote add default https://conandev.jfrog.io/artifactory/api/conan/abril-tests")
        tc.run("remote login default abril")
        tc.run("remove * -c -r=default")
        cppstds = [7 + i*3 for i in range(factors+1)]
        compiler_settings = textwrap.dedent(f"""
                compiler:
                    foo:
                        version: [1]
                        cppstd: {cppstds}""")
        tc.run("version")
        tc.save_home({"settings_user.yml": compiler_settings})
        compat = tc.load_home("extensions/plugins/compatibility/compatibility.py")
        compat = compat.replace("cppstd_possible_values = supported_cppstd(conanfile)",
                                f"cppstd_possible_values = {cppstds}")
        tc.save_home({"extensions/plugins/compatibility/compatibility.py": compat})
        threshold = -1 if with_optimization else 1
        tc.save_home({"global.conf": f"user.graph:compatibility_optimization_threshold={factors + threshold}"})

        compiler_args = "-s compiler=foo -s compiler.version=1"
        pkg_name = str(time.time())
        tc.save({"conanfile.py": GenConanfile(pkg_name, "0.1").with_settings("compiler")})

        if with_optimization:
            for i in range(factors-1):
                tc.run(f"create . {compiler_args} -s compiler.cppstd={7 + i*3} -nr")
        tc.run(f"create . {compiler_args} -s compiler.cppstd={7 + (factors-1)*3} -nr")

        tc.run("upload * -r=default -c")
        tc.run("remove *:* -c")

        start_time = time.time()
        tc.run(f"install --requires={pkg_name}/0.1 {compiler_args} -s compiler.cppstd={7 + factors*3}")
        end_time = time.time()
        if with_optimization:
            assert f"Found {factors} compatible configurations in remotes" in tc.out
        else:
            assert f"compatible configurations in remotes" not in tc.out
        duration = end_time - start_time
        timings.append((factors, runs, with_optimization, duration))
