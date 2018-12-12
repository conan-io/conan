import argparse
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


"""
PYVERS=py27,py36,py37
CI_TAGS=svn or now slow





"""