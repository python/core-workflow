Setup Info
==========

Requires Python 3.6 and virtualenv.

::

    $ git clone https://github.com/Mariatta/chic_a_cherry_picker.git
    $ cd chic_a_cherry_picker
    $ virtualenv venv
    $ source venv/bin/activate
    $ pip install -r requirements.txt
    $ git clone https://github.com/Mariatta/cpython.git
    $ cd cpython
    $ git remote add upstream https://github.com/Mariatta/cpython.git
    $ cd ../


Cherry-picking
==============

(Setup first! See prev section)

::

    $ python -m cherry_picker <commit_sha1> <branches>


For example, to cherry-pick `6de2b7817fa9403e81dc38f13f3690f0bbf3d064` into
`3.5` and `3.6`:

::

    $ python -m cherry_picker 6de2b7817fa9403e81dc38f13f3690f0bbf3d064 3.5 3.6


What this will do:

::

    $ cd cpython
    $ git fetch upstream
    $ git checkout -b 6de2b78-3.5 upstream/3.5
    $ git cherry-pick -x 6de2b7817fa9403e81dc38f13f3690f0bbf3d064
    $ git push origin 6de2b78-3.5
    $ git checkout master
    $ git branch -D 6de2b78-3.5
    $ git checkout -b 6de2b78-3.6 upstream/3.6
    $ git cherry-pick -x 6de2b7817fa9403e81dc38f13f3690f0bbf3d064
    $ git push origin 6de2b78-3.6
    $ git checkout master


Then go to https://github.com/python/cpython to create the pull requests.
