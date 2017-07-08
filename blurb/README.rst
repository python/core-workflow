blurb
=====

.. image:: https://img.shields.io/pypi/v/blurb.svg
    :target: https://pypi.org/project/blurb/

Overview
--------

**blurb** is a tool designed to rid CPython core development
of the scourge of ``Misc/NEWS`` conflicts.

The core concept: split ``Misc/NEWS`` into many
separate files that, when concatenated back together
in sorted order, reconstitute the original ``Misc/NEWS`` file.
After that, ``Misc/NEWS`` could be deleted from the CPython
repo and thereafter rendered on demand (e.g. when building
a release).  When checking in a change to CPython, the checkin
process will write out a new file that sorts into the correct place,
using a filename unlikely to have a merge conflict.

**blurb** is a single command with a number of subcommands.
It's designed  to be run inside a valid CPython (git) repo,
and automatically uses the correct file paths.

You can install **blurb** from PyPI using ``pip``.  Alternatively,
simply add ``blurb`` to a directory on your path.
**blurb**'s only dependency is Python 3.5+.


Files used by blurb
-------------------

**blurb** uses a new directory tree called ``Misc/NEWS.d``.
Everything it does is in there, except for possibly
modifying ``Misc/NEWS``.

Under ``Misc/NEWS.d`` you'll find the following:

* A single file for all news entries per previous revision,
  named for the exact version number, with the extension ``.rst``.
  Example: ``Misc/NEWS.d/3.6.0b2.rst``.

* The ``next`` directory, which contains subdirectories representing
  the various ``Misc/NEWS`` categories.  Inside these subdirectories
  are more ``.rst`` files with long, uninteresting, computer-generated
  names.  Example:
  ``Misc/NEWS.d/next/Library/2017-05-04-12-24-06.bpo-25458.Yl4gI2.rst``


blurb subcommands
-----------------

Like many modern utilities, **blurb** has only one executable
(called ``blurb``), but provides a diverse set of functionality
through subcommands.  The subcommand is the first argument specified
on the command-line.

If you're a CPython core developer, you probably don't need to use
anything except ``blurb add``--and you don't even need to specify
the ``add`` part.
(If no subcommand is specified, **blurb** assumes you meant ``blurb add``.)
The other commands are only expected to be useful for CPython release
managers.



blurb help
~~~~~~~~~~

**blurb** is self-documenting through the ``blurb help`` subcommand.
Run without any further arguments, it prints a list of all subcommands,
with a one-line summary of the functionality of each.  Run with a
third argument, it prints help on that subcommand (e.g. ``blurb help release``).


blurb add
~~~~~~~~~

``blurb add`` adds a new Misc/NEWS entry for you.
It opens a text editor on a template; you edit the
file, save, and exit.  **blurb** then stores the file
in the correct place, and stages it in ``git`` for you.

The template for the ``blurb add`` message looks like this::

    #
    # Please enter the relevant bugs.python.org issue number here:
    #
    .. bpo:

    #
    # Uncomment one of these "section:" lines to specify which section
    # this entry should go in in Misc/NEWS.
    #
    #.. section: Security
    #.. section: Core and Builtins
    #.. section: Library
    #.. section: Documentation
    #.. section: Tests
    #.. section: Build
    #.. section: Windows
    #.. section: macOS
    #.. section: IDLE
    #.. section: Tools/Demos
    #.. section: C API

    # Write your Misc/NEWS entry below.  It should be a simple ReST paragraph.
    # Don't start with "- Issue #<n>: " or "- bpo-<n>: "or that sort of stuff.
    ###########################################################################

Here's how you interact with the file:

* Add the ``bugs.python.org`` issue number for this checkin to the
  end of the ``.. bpo:`` line.

* Uncomment the line with the relevant ``Misc/NEWS`` section for this entry.
  For example, if this should go in the ``Library`` section, uncomment
  the line reading ``#.. section: Library``.  To uncomment, just delete
  the ``#`` at the front of the line.

* Finally, go to the end of the file, and enter your NEWS entry.
  This should be a single paragraph of English text using
  simple ReST markup.

When ``blurb add`` gets a valid entry, it writes it to a file
with the following format::

    Misc/NEWS.d/next/<section>/<datetime>.bpo-<bpo>.<nonce>.rst

For example, a file added by ``blurb add`` might look like this::

    Misc/NEWS.d/next/Library/2017-05-04-12-24-06.bpo-25458.Yl4gI2.rst

``<section>`` is the section provided in the checkin message.

``<datetime>`` is the current UTC time, formatted as
``YYYY-MM-DD-hh-mm-ss``.

``<nonce>`` is a hopefully-unique string of characters meant to
prevent filename collisions.  **blurb** creates this by computing
the MD5 hash of the text, converting it to base64 (using the
"urlsafe" alphabet), and taking the first 6 characters of that.


This filename ensures several things:

* All entries in ``Misc/NEWS`` will be sorted by time.

* It is unthinkably unlikely that there'll be a conflict
  between the filenames generated for two developers checking in,
  even if they check in at the exact same second.


Finally, ``blurb add`` stages the file in git for you.


blurb merge
~~~~~~~~~~~

``blurb merge`` recombines all the files in the
``Misc/NEWS.d`` tree back into a single ``NEWS`` file.

``blurb merge`` accepts only a single command-line argument:
the file to write to.  By default it writes to
``Misc/NEWS`` (relative to the root of your CPython checkout).

Splitting and recombining the existing ``Misc/NEWS`` file
doesn't recreate the previous ``Misc/NEWS`` exactly.  This
is because ``Misc/NEWS`` never used a consistent ordering
for the "sections" inside each release, whereas ``blurb merge``
has a hard-coded preferred ordering for the sections.  Also,
**blurb** aggressively reflows paragraphs to < 78 columns,
wheras the original hand-edited file occasionally had lines
> 80 columns.  Finally, **blurb** strictly uses ``bpo-<n>:`` to
specify issue numbers at the beginnings of entries, wheras
the legacy approach to ``Misc/NEWS`` required using ``Issue #<n>:``.


blurb release
~~~~~~~~~~~~~

``blurb release`` is used by the release manager as part of
the CPython release process.  It takes exactly one argument,
the name of the version being released.

Here's what it does under the hood:

* Combines all recently-added NEWS entries from
  the ``Misc/NEWS.d/next`` directory into ``Misc/NEWS.d/<version>.rst``.
* Runs ``blurb merge`` to produce an updated ``Misc/NEWS`` file.

One hidden feature: if the version specified is ``.``, ``blurb release``
uses the name of the directory CPython is checked out to.
(When making a release I generally name the directory after the
version I'm releasing, and using this shortcut saves me some typing.)


blurb split
~~~~~~~~~~~

``blurb split`` only needs to be run once per-branch, ever.
It reads in ``Misc/NEWS``
and splits it into individual ``.rst`` files.
The text files are stored as follows::

    Misc/NEWS.d/<version>.rst

``<version>`` is the version number of Python where the
change was committed.  Pre-release versions are denoted
with an abbreviation: ``a`` for alphas, ``b`` for betas,
and ``rc`` for release candidates.

The individual ``<version>.rst`` files actually (usually)
contain multiple entries.  Each entry is delimited by a
single line containing ``..`` by itself.

The assumption is, at the point we convert over to *blurb*,
we'll run ``blurb split`` on each active branch,
remove ``Misc/NEWS`` from the repo entirely,
never run ``blurb split`` ever again,
and ride off into the sunset, confident that the world is now
a better place.



The "next" directory
--------------------

You may have noticed that ``blurb add`` adds news entries to
a directory called ``next``, and ``blurb release`` combines those
news entries into a single file named with the version.  Why
is that?

First, it makes naming the next version a late-binding decision.
If we are currently working on 3.6.5rc1, but there's a zero-day
exploit and we need to release an emergency 3.6.5 final, we don't
have to fix up a bunch of metadata.

Second, it means that if you cherry-pick a commit forward or
backwards, you automatically pick up the NEWS entry too.  You
don't need to touch anything up--the system will already do
the right thing.  If NEWS entries were already written to the
final version directory, you'd have to move those around as
part of the cherry-picking process.


Copyright
---------

**blurb** is Copyright 2015-2017 by Larry Hastings.
Licensed to the PSF under a contributor agreement.
