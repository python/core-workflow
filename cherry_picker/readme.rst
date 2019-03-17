Usage (from a cloned CPython directory) ::

   cherry_picker [--pr-remote REMOTE] [--dry-run] [--config-path CONFIG-PATH] [--status] [--abort/--continue] [--push/--no-push] <commit_sha1> <branches>

|pyversion status|
|pypi status|
|travis status|

.. contents::

About
=====

This tool is used to backport CPython changes from ``master`` into one or more
of the maintenance branches (``3.6``, ``3.5``, ``2.7``).

``cherry_picker`` can be configured to backport other projects with similar
workflow as CPython. See the configuration file options below for more details.

The maintenance branch names should contain some sort of version number (X.Y).
For example: ``3.6``, ``3.5``, ``2.7``, ``stable-2.6``, ``2.5-lts``, are all 
supported branch names.

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
   fix_commit_msg = false
   default_branch = "devel"


Available config options::

   team            github organization or individual nick,
                   e.g "aio-libs" for https://github.com/aio-libs/aiohttp
                   ("python" by default)

   repo            github project name,
                   e.g "aiohttp" for https://github.com/aio-libs/aiohttp
                   ("cpython" by default)

   check_sha       A long hash for any commit from the repo,
                   e.g. a sha1 hash from the very first initial commit
                   ("7f777ed95a19224294949e1b4ce56bbffcb1fe9f" by default)

   fix_commit_msg  Replace # with GH- in cherry-picked commit message.
                   It is the default behavior for CPython because of external
                   Roundup bug tracker (https://bugs.python.org) behavior:
                   #xxxx should point on issue xxxx but GH-xxxx points
                   on pull-request xxxx.
                   For projects using GitHub Issues, this option can be disabled.

   repo            Project's default branch name,
                   e.g "devel" for https://github.com/ansible/ansible
                   ("master" by default)


To customize the tool for used by other project:

1. Create a file called ``.cherry_picker.toml`` in the project's root
   folder (alongside with ``.git`` folder).

2. Add ``team``, ``repo``, ``fix_commit_msg``, ``check_sha`` and
   ``default_branch`` config values as described above.

3. Use ``git add .cherry_picker.toml`` / ``git commit`` to add the config
   into ``git``.

4. Add ``cherry_picker`` to development dependencies or install it
   by ``pip install cherry_picker``

5. Now everything is ready, use ``cherry_picker <commit_sha> <branch1>
   <branch2>`` for cherry-picking changes from ``<commit_sha>`` into
   maintenance branches.
   Branch name should contain at least major and minor version numbers
   and may have some prefix or suffix.
   Only the first version-like substring is matched when the version
   is extracted from branch name.

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

`--config-path` option
----------------------

Allows to override default config file path
(``<PROJ-ROOT>/.cherry_picker.toml``) with a custom one. This allows cherry_picker
to backport projects other than CPython.


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

- Create a new release branch.

- Update the version info in ``__init__.py`` and ``readme.rst``, dropping the ``.dev``.

- Tag the branch as ``cherry-picker-vX.Y.Z``.


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

Changelog
=========

1.3.1 (in development)
----------------------

- Modernize cherry_picker's pyproject.toml file. (`PR #316 <https://github.com/python/core-workflow/pull/316>`_)

- Remove the ``BACKPORT_COMPLETE`` state. Unset the states when backport is completed.
  (`PR #315 <https://github.com/python/core-workflow/pull/315>`_)

- Run Travis CI test on Windows (`PR #311 <https://github.com/python/core-workflow/pull/311>`_).

1.3.0
-----

- Implement state machine and storing reference to the config
  used at the beginning of the backport process using commit sha
  and a repo-local Git config.
  (`PR #295 <https://github.com/python/core-workflow/pull/295>`_).

1.2.2
-----

- Relaxed click dependency (`PR #302 <https://github.com/python/core-workflow/pull/302>`_).

1.2.1
-----

- Validate the branch name to operate on with ``--continue`` and fail early if the branch could not
  have been created by cherry_picker. (`PR #266 <https://github.com/python/core-workflow/pull/266>`_).

- Bugfix: Allow ``--continue`` to support version branches that have dashes in them.  This is
  a bugfix of the additional branch versioning schemes introduced in 1.2.0.
  (`PR #265 <https://github.com/python/core-workflow/pull/265>`_).

- Bugfix: Be explicit about the branch name on the remote to push the cherry pick to.  This allows
  cherry_picker to work correctly when the user has a git push strategy other than the default
  configured. (`PR #264 <https://github.com/python/core-workflow/pull/264>`_).

1.2.0
-----

- Add ``default_branch`` configuration item. The default is ``master``, which
  is the default branch for CPython. It can be configured to other branches like,
  ``devel``, or ``develop``.  The default branch is the branch cherry_picker
  will return to after backporting. (`PR #254 <https://github.com/python/core-workflow/pull/254>`_
  and `Issue #250 <https://github.com/python/core-workflow/issues/250>`_).

- Support additional branch versioning schemes, such as ``something-X.Y``,
  or ``X.Y-somethingelse``. (`PR #253 <https://github.com/python/core-workflow/pull/253>`_
  and `Issue #251 <https://github.com/python/core-workflow/issues/251>`_).

1.1.1
-----

- Change the calls to ``subprocess`` to use lists instead of strings. This fixes
  the bug that affects users in Windows. (`PR #238 <https://github.com/python/core-workflow/pull/238>`_).

1.1.0
-----

- Add ``fix_commit_msg`` configuration item. Setting fix_commit_msg to ``true``
  will replace the issue number in the commit message, from ``#`` to ``GH-``.
  This is the default behavior for CPython. Other projects can opt out by
  setting it to ``false``. (`PR #233 <https://github.com/python/core-workflow/pull/233>`_
  and `aiohttp Issue #2853 <https://github.com/aio-libs/aiohttp/issues/2853>`_).

1.0.0
-----

- Support configuration file by using ``--config-path`` option, or by adding
  ``.cherry-picker.toml`` file to the root of the project. (`Issue #225
  <https://github.com/python/core-workflow/issues/225>`_).
