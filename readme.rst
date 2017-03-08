.. contents::

Setup Info
==========

Requires Python 3.6 and virtualenv.

::

    $ git clone https://github.com/Mariatta/chic_a_cherry_picker.git
    $ cd chic_a_cherry_picker
    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install -r requirements.txt
    (venv) $ git clone https://github.com/Mariatta/cpython.git  #or your own cpython fork
    (venv) $ cd cpython
    (venv) $ git remote add upstream https://github.com/python/cpython.git
    (venv) $ cd ../


Cherry-picking
==============

(Setup first! See prev section)

::

    (venv) $ python -m cherry_picker <commit_sha1> <branches>

The commit sha1 is obtained from the merged pull request on master. 

For example, to cherry-pick ``6de2b7817f-some-commit-sha1-d064`` into
``3.5`` and ``3.6``:

::

    (venv) $ python -m cherry_picker 6de2b7817f-some-commit-sha1-d064 3.5 3.6


What this will do:

::

    (venv) $ cd cpython
    
    (venv) $ git fetch upstream
    
    (venv) $ git checkout -b 6de2b78-3.5 upstream/3.5
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064 
    (venv) $ git push origin 6de2b78-3.5
    (venv) $ git checkout master
    (venv) $ git branch -D 6de2b78-3.5
    
    (venv) $ git checkout -b 6de2b78-3.6 upstream/3.6
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064 
    (venv) $ git push origin 6de2b78-3.6
    (venv) $ git checkout master
    (venv) $ git branch -D 6de2b78-3.6

In case of merge conflicts or errors, then... the script will fail :P


Creating Pull Requests
======================

When a cherry-pick was applied successfully, this script will open up a browser
tab that points to the pull request creation page.

The url of the pull request page looks similar to the following::

   https://github.com/python/cpython/compare/3.5...Mariatta:6de2b78-3.5?expand=1



1. Prefix the pull request description with the branch ``[X.Y]``, e.g.::

     [3.6] bpo-xxxxx: Fix this and that

2. Apply the appropriate ``cherry-pick for ...`` label

3. Press the ``Create Pull Request`` button.

4. Remove the ``needs backport to ...`` label from the original pull request
   against ``master``.
