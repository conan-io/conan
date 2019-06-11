import argparse
import json
import os


from github import Github


def _get_value(body, tag):
    pos = body.lower().find(tag.lower())
    if pos != -1:
        cl = body[pos + len(tag):].splitlines()[0]
        return cl.strip()
    return None


def get_tag_from_pr(pr_number, tag):
    """Given a PR number and a tag to search, it returns the line written in the body"""
    gh_token = os.getenv("GH_TOKEN")
    g = Github(gh_token)
    repo = g.get_repo("conan-io/conan")
    pr = repo.get_pull(pr_number)
    body = pr.body
    value = _get_value(body, tag)
    return value


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Launch tests in a venv')
    parser.add_argument('output_file', help='e.g.: file.json')
    parser.add_argument('branch_name', help='e.g.: PR-23')
    args = parser.parse_args()

    TAG_PYVERS = "@PYVERS:"
    TAG_TAGS = "@TAGS:"
    TAG_REVISIONS = "@REVISIONS:"

    out_file = args.output_file
    branch = args.branch_name

    if not branch.startswith("PR-"):
        print("The branch is not a PR")
        exit(-1)
    pr_number = int(branch.split("PR-")[1])


    def clean_list(the_list):
        if not the_list:
            return []
        return [a.strip() for a in the_list.split(",")]

    # Read tags to include
    tags = clean_list(get_tag_from_pr(pr_number, TAG_TAGS))
    # Read pythons to include
    tmp = clean_list(get_tag_from_pr(pr_number, TAG_PYVERS))
    pyvers = {"Windows": [], "Linux": [], "Macos": []}
    for t in tmp:
        if "@" in t:
            the_os, pyver = t.split("@")
            if the_os not in ["Macos", "Linux", "Windows"]:
                print("Invalid os: %s" % the_os)
                exit(-1)
            pyvers[the_os].append(pyver)
        else:
            pyvers["Macos"].append(t)
            pyvers["Linux"].append(t)
            pyvers["Windows"].append(t)

    # Rest revisions?
    tmp = get_tag_from_pr(pr_number, TAG_REVISIONS)
    revisions = tmp.strip().lower() in ["1", "true"] if tmp else False

    with open(out_file, "w") as f:
        the_json = {"tags": tags, "pyvers": pyvers, "revisions": revisions}
        f.write(json.dumps(the_json))
