import glob
import os
import sys
import xml.etree.ElementTree as ET

PREDICTION_FILE = "covtest-prediction/covtests.tests"


def nodeid_to_junit_key(nodeid):
    """Convert 'test/path.py::Class::method' to 'test.path.Class::method' (JUnit classname::name)."""
    parts = nodeid.split("::")
    file_part = parts[0].replace("\\", "/")
    module = file_part.replace("/", ".")
    if module.endswith(".py"):
        module = module[:-3]
    if len(parts) <= 1:
        return module + "::"
    elif len(parts) == 2:
        return module + "::" + parts[1]
    else:
        return module + "." + ".".join(parts[1:-1]) + "::" + parts[-1]


def main():
    if not os.path.exists(PREDICTION_FILE):
        prediction_note = "Prediction file not found -- skipping comparison."
        raw_predictions = []
    else:
        with open(PREDICTION_FILE) as f:
            raw_predictions = [line.strip() for line in f if line.strip()]
        if not raw_predictions:
            prediction_note = "Empty prediction (server unreachable, no snapshot, or config changed) -- skipping comparison."
        else:
            prediction_note = None

    predicted_keys = {nodeid_to_junit_key(n) for n in raw_predictions}

    total_run = total_failures_attr = total_errored = total_skipped = 0
    suite_count = 0
    failing_keys = set()

    for xml_file in glob.glob("test-results/**/*.xml", recursive=True):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as e:
            print("::warning::Could not parse {}: {}".format(xml_file, e))
            continue
        for suite in root.iter("testsuite"):
            suite_count += 1
            total_run += int(suite.get("tests", 0))
            total_failures_attr += int(suite.get("failures", 0))
            total_errored += int(suite.get("errors", 0))
            total_skipped += int(suite.get("skipped", 0))
        for tc in root.iter("testcase"):
            if tc.find("failure") is not None or tc.find("error") is not None:
                key = tc.get("classname", "") + "::" + tc.get("name", "")
                failing_keys.add(key)

    total_failing = len(failing_keys)
    total_passed = total_run - total_failing - total_skipped

    print("=== CovTest Prediction Summary ===")
    print("Tests run:        {:>6,}  (across {} suites)".format(total_run, suite_count))
    print("  Passed:         {:>6,}".format(total_passed))
    print("  Failed/Errored: {:>6,}".format(total_failing))
    print("  Skipped:        {:>6,}".format(total_skipped))
    print()

    if prediction_note:
        print(prediction_note)
        return 0

    print("Covtest predicted:{:>6,} tests".format(len(raw_predictions)))

    if total_failing == 0:
        print("  No test failures -- nothing to validate.")
        return 0

    unpredicted = failing_keys - predicted_keys
    predicted_hit = total_failing - len(unpredicted)
    pct = predicted_hit / total_failing * 100
    print("  Predicted failures:   {:>3} / {}  ({:.1f}%)".format(predicted_hit, total_failing, pct))
    print("  Unpredicted failures: {:>3} / {}  ({:.1f}%)".format(len(unpredicted), total_failing, 100 - pct))
    print()

    if not unpredicted:
        print("All failing tests were predicted by covtest. OK.")
        return 0

    print("Prediction hit rate (failed tests): {:.1f}%".format(pct))
    print()
    print("Unpredicted failures:")
    for key in sorted(unpredicted):
        print("  {}".format(key))
        print("::warning::Unpredicted test failure: {}".format(key))

    return 0


if __name__ == "__main__":
    sys.exit(main())
