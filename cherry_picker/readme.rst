Usage (from a cloned CPython directory) ::

   cherry_picker [--pr-remote REMOTE] [--dry-run] [--status] [--abort/--continue] [--push/--no-push] <commit_sha1> <branches>

|pyversion status|
|pypi status|
|travis status|

.. contents::

About
=====

Use this to backport CPython changes from ``master`` into one or more of the
maintenance branches (``3.6``, ``3.5``, ``2.7``).

It will prefix the commit message with the branch, e.g. ``[3.6]``, and then
opens up the pull request page.

Tests are to be written using `pytest <https://docs.pytest.org/en/latest/>`_.


Setup Info
==========

Requires Python 3.6.

::

    $ python3 -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install cherry_picker

The cherry picking script assumes that if an ``upstream`` remote is defined, then
it should be used as the source of upstream changes and as the base for
cherry-pick branches. Otherwise, ``origin`` is used for that purpose.

Verify that an ``upstream`` remote is set to the CPython repository::

    $ git remote -v
    ...
    upstream	https://github.com/python/cpython (fetch)
    upstream	https://github.com/python/cpython (push)

If needed, create the ``upstream`` remote::

    $ git remote add upstream https://github.com/python/cpython.git


By default, the PR branches used to submit pull requests back to the main
repository are pushed to ``origin``. If this is incorrect, then the correct
remote will need be specified using the ``--pr-remote`` option (e.g.
``--pr-remote pr`` to use a remote named ``pr``).


Cherry-picking 🐍🍒⛏️
=====================

(Setup first! See prev section)

From the cloned CPython directory:

::

    (venv) $ cherry_picker [--pr-remote REMOTE] [--dry-run] [--config-path CONFIG-PATH] [--abort/--continue] [--status] [--push/--no-push] <commit_sha1> <branches>


Commit sha1
-----------

The commit sha1 for cherry-picking is the squashed commit that was merged to
the ``master`` branch.  On the merged pull request, scroll to the bottom of the
page.  Find the event that says something like::

   <coredeveloper> merged commit <commit_sha1> into python:master <sometime> ago.

By following the link to ``<commit_sha1>``, you will get the full commit hash.
Use the full commit hash for ``cherry_picker.py``.


Options
-------

::

    -- dry-run           Dry Run Mode.  Prints out the commands, but not executed.
    -- pr-remote REMOTE  Specify the git remote to push into.  Default is 'origin'.
    -- status            Do `git status` in cpython directory.


Additional options::

    -- abort        Abort current cherry-pick and clean up branch
    -- continue     Continue cherry-pick, push, and clean up branch
    -- no-push      Changes won't be pushed to remote
    -- config-path  Path to config file
                    (`.cherry_picker.toml` from project root by default)


Configuration file example::

   team = "aio-libs"
   repo = "aiohttp"
   check_sha = "f382b5ffc445e45a110734f5396728da7914aeb6"

Available config options::

   team        github organization or individual nick,
               e.g "aio-libs" for https://github.com/aio-libs/aiohttp
               ("python" by default)

   repo        github project name,
               e.g "aiohttp" for https://github.com/aio-libs/aiohttp
               ("cpython" by default)

   check_sha   A long hash for any commit from the repo,
               e.g. a sha1 hash from the very first initial commit
               ("7f777ed95a19224294949e1b4ce56bbffcb1fe9f" by default)

To setup the tool for using by custom project:

1. Create a file called `.cherry_picker.toml` in the project's root
   folder (alongside with `.git` forlder).

2. Add `team`, `repo` and `check_sha` config values as described above.

3. Use `git add .cherry_picker.toml` / `git commit` to add the config
   into git.

4. Add `cherry_picker` to development dependencies or just install it
   by `pip install cherry_picker`

5. Now everything is ready, use `cherry_picker <commit_sha> <branch1>
   <branch2>` for cherry-picking changes from `<commit_sha` into
   maintainance branches.

Demo
----

- Installation: https://asciinema.org/a/125254

- Backport: https://asciinema.org/a/125256


Example
-------

For example, to cherry-pick ``6de2b7817f-some-commit-sha1-d064`` into
``3.5`` and ``3.6``, run the following command from the cloned CPython
directory:

::

    (venv) $ cherry_picker 6de2b7817f-some-commit-sha1-d064 3.5 3.6


What this will do:

::

    (venv) $ git fetch upstream

    (venv) $ git checkout -b backport-6de2b78-3.5 upstream/3.5
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064
    (venv) $ git push origin backport-6de2b78-3.5
    (venv) $ git checkout master
    (venv) $ git branch -D backport-6de2b78-3.5

    (venv) $ git checkout -b backport-6de2b78-3.6 upstream/3.6
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064
    (venv) $ git push origin backport-6de2b78-3.6
    (venv) $ git checkout master
    (venv) $ git branch -D backport-6de2b78-3.6

In case of merge conflicts or errors, the following message will be displayed::

    Failed to cherry-pick 554626ada769abf82a5dabe6966afa4265acb6a6 into 2.7 :frowning_face:
    ... Stopping here.

    To continue and resolve the conflict:
        $ cherry_picker --status  # to find out which files need attention
        # Fix the conflict
        $ cherry_picker --status  # should now say 'all conflict fixed'
        $ cherry_picker --continue

    To abort the cherry-pick and cleanup:
        $ cherry_picker --abort


Passing the ``--dry-run`` option will cause the script to print out all the
steps it would execute without actually executing any of them. For example::

    $ cherry_picker --dry-run --pr-remote pr 1e32a1be4a1705e34011770026cb64ada2d340b5 3.6 3.5
    Dry run requested, listing expected command sequence
    fetching upstream ...
    dry_run: git fetch origin
    Now backporting '1e32a1be4a1705e34011770026cb64ada2d340b5' into '3.6'
    dry_run: git checkout -b backport-1e32a1b-3.6 origin/3.6
    dry_run: git cherry-pick -x 1e32a1be4a1705e34011770026cb64ada2d340b5
    dry_run: git push pr backport-1e32a1b-3.6
    dry_run: Create new PR: https://github.com/python/cpython/compare/3.6...ncoghlan:backport-1e32a1b-3.6?expand=1
    dry_run: git checkout master
    dry_run: git branch -D backport-1e32a1b-3.6
    Now backporting '1e32a1be4a1705e34011770026cb64ada2d340b5' into '3.5'
    dry_run: git checkout -b backport-1e32a1b-3.5 origin/3.5
    dry_run: git cherry-pick -x 1e32a1be4a1705e34011770026cb64ada2d340b5
    dry_run: git push pr backport-1e32a1b-3.5
    dry_run: Create new PR: https://github.com/python/cpython/compare/3.5...ncoghlan:backport-1e32a1b-3.5?expand=1
    dry_run: git checkout master
    dry_run: git branch -D backport-1e32a1b-3.5

`--pr-remote` option
--------------------

This will generate pull requests through a remote other than ``origin``
(e.g. ``pr``)


`--status` option
-----------------

This will do ``git status`` for the CPython directory.

`--abort` option
----------------

Cancels the current cherry-pick and cleans up the cherry-pick branch.

`--continue` option
-------------------

Continues the current cherry-pick, commits, pushes the current branch to
``origin``, opens the PR page, and cleans up the branch.

`--no-push` option
------------------

Changes won't be pushed to remote.  This allows you to test and make additional
changes.  Once you're satisfied with local changes, use ``--continue`` to complete
the backport, or ``--abort`` to cancel and clean up the branch.  You can also
cherry-pick additional commits, by::

   $ git cherry-pick -x <commit_sha1>


Creating Pull Requests
======================

When a cherry-pick was applied successfully, this script will open up a browser
tab that points to the pull request creation page.

The url of the pull request page looks similar to the following::

   https://github.com/python/cpython/compare/3.5...<username>:backport-6de2b78-3.5?expand=1


Press the ``Create Pull Request`` button.

Bedevere will then remove the ``needs backport to ...`` label from the original
pull request against ``master``.


Running Tests
=============

Install pytest: ``pip install -U pytest``

::

    $ pytest test.py


Publishing to PyPI
==================

Publish to PyPI using `flit <https://flit.readthedocs.io/en/latest/>`_.

Install flit (preferably in a virtual environment)::

    python3 -m pip install flit

In the directory where ``pyproject.toml`` exists::

    flit publish


Local installation
==================

With `flit <https://flit.readthedocs.io/en/latest/>`_ installed,
in the directory where ``pyproject.toml`` exists::

    flit install


.. |pyversion status| image:: https://img.shields.io/pypi/pyversions/cherry-picker.svg
   :target: https://pypi.org/project/cherry-picker/

.. |pypi status| image:: https://img.shields.io/pypi/v/cherry-picker.svg
   :target: https://pypi.org/project/cherry-picker/

.. |travis status| image:: https://travis-ci.org/python/core-workflow.svg?branch=master
   :target: https://travis-ci.org/python/core-workflow

