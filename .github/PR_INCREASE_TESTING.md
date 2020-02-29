Increasing testing level in the Pull Requests
=============================================

By default the PRs will skip the slower tests and will use a limited set of python versions. 
Use the following tags in the body of the Pull Request:

```
#PYVERS: Macos@py27, Windows@py36, Linux@py27, py34
#TAGS: svn, slow
#REVISIONS: 1
```

- **#PYVERS** adds new python versions to the slaves, it can be scoped to a slave with a @ (Macos, Windows, Linux) or 
  global for all.
- **#TAGS** adds tags (removes the excluded, by default "slow" and "svn" are excluded. Add them to run all tests).
- **#REVISIONS** enable the three revisions stages, can be '1' or 'True'.
