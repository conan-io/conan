Contributing to Conan
*********************

The following summarizes the process for contributing to the Conan project.


Community
=========

Conan is an Open Source MIT licensed project. 

Conan is developed by the Conan maintainers and a great community of contributors.


Dev-flow && Pull Requests
========================

Conan follows the ["GitFlow"](https://datasift.github.io/gitflow/IntroducingGitFlow.html) branching model. 
To contribute:

1. Comment in the corresponding issue that you are doing this. If there is no open issue, we strongly suggest to open one for feedback.
2. Fork the [Conan main repository](https://github.com/conan-io/conan).
3. Create a `feature/xxx` branch from the ``develop`` branch and develop your feature.
4. Try to keep your branch updated with the ``develop`` branch to avoid conflicts.
5. Open a pull request, and select ``develop`` as the base branch. Never open a pull request to ``master``
 or ``release/xxx`` branches.
6. Add the text (besides other comments): "Implements #IssueNumber" in the body of the PR, refering to the issue of step 1)
 
 
The ``conan-io`` organization users will prioritize the Issues and will assign them to a Milestone accordingly. 

Each milestone corresponds to a Conan release, a branch ``release/xxx`` will be opened from the ``develop`` branch.
When the branch is ready, it will be merged into ``master`` branch and a TAG corresponding to the version will be pushed.

The ``conan-io`` organization users reserve the right of altering the Milestones and the issues of each Milestone,
as well as the release dates.


Issues
======

If you think you found a bug in Conan:

- Explain the Conan version, Operating System, compiler and any other tool that could be related to the issue.
- Explain, as detailed as possible, how to reproduce the issue. Use git repos to contain code/recipes to reproduce issues.
- Include what you expected to happen, as well as what actually happened.
- Provide output captures (as text).
- If it helps, feel free to attach a screenshot or video illustrating the issue.


For any suggestion, feature request or question:

- Questions and support requests are very welcome. 
- Use the [question] or [bug] tags in the title.
- Try to explain the motivation, what are you trying to do, what is the pain to try to solve.
- What do you expect from Conan.

We use the following tags to control the state of the issues:

- **bug**: If a bug is confirmed (or looks like one). We have other tags like **enhancement** if
  it's not a bug but a feature.
- **fixed**: A fix (or feature) has been merged to develop, so will be fixed in the next release.
- **closed**: The Conan version contaning the fix or feature has been released.

So, please, even if the bug is solved in develop, do not close the issue, we prefer to keep it open 
and at **fixed** state to keep track of all of them.


Code of conduct
===============

Try to be polite, Conan maintainers and contributors are really willing to help, and we enjoy it. Please understand that:

- There are limited resources/time, not all issues/pull requests can be attended as we would like.
- ``conan-io`` maintainers can tag/close/modify any opened issue.
  It should not be interpreted as a rude or disrespectful act. It **always** responds to organizational purposes.
  A closed issue can be perfectly reopened, commented by the author or Conan maintainers.
- It is very hard to keep the project in good health in terms of technical debt, usability, serviceability, etc. 
  So, if we are not fully sure of a proposed feature or a pull request or we don't have information enough to be 
  sure that it's a good feature for the project, it won't be accepted until we are sure. The community 
  plays a very important role here, explain the value of a feature for the community, and the needed documentation and use cases.
  Backwards compatibility and not breaking users packages is very important, and won't be done unless there are very good reasons.
- You should not get bothered if you feel unattended, Conan is an Open Source project, not a commercial product, try
  to explain why you really need what you need, we will try to help you.
