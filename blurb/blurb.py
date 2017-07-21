#!/usr/bin/env python3
"""Command-line tool to manage CPython Misc/NEWS.d entries."""
__version__ = "1.0.3"

##
## blurb version 1.0
## Part of the blurb package.
## Copyright 2015-2017 by Larry Hastings
##
## Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are
## met:
##
## 1. Redistributions of source code must retain the above copyright
## notice, this list of conditions and the following disclaimer.
##
## 2. Redistributions in binary form must reproduce the above copyright
## notice, this list of conditions and the following disclaimer in the
## documentation and/or other materials provided with the distribution.
##
## 3. Neither the name of the copyright holder nor the names of its
## contributors may be used to endorse or promote products derived from
## this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
## IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
## TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
## PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
## TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
## PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
## LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
## NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
## SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
##
##
## Licensed to the Python Software Foundation under a contributor agreement.
##


# TODO
#
# automatic git adds and removes

import atexit
import base64
import builtins
from collections import OrderedDict
import glob
import hashlib
import inspect
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types
import unittest
import uuid


#
# This template is the canonical list of acceptable section names!
# It's parsed internally into the "sections" set.
#

template = """

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
# Don't start with "- Issue #<n>: " or "- bpo-<n>: " or that sort of stuff.
###########################################################################


""".lstrip()

root = None
original_dir = None
sections = []

for line in template.split('\n'):
    line = line.strip()
    prefix, found, section = line.partition("#.. section: ")
    if found and not prefix:
        sections.append(section.strip())


def sanitize_section(section):
    """
Cleans up a section string, making it viable as a directory name.
    """
    return section.replace("/", "-")

_unsanitize_section = {
    "Tools-Demos": "Tools/Demos",
    }

def unsanitize_section(section):
    return _unsanitize_section.get(section, section)


def textwrap_body(body, *, subsequent_indent=''):
    """
    Accepts either a string or an iterable of strings.
    (Iterable is assumed to be individual lines.)
    Returns a string.
    """
    if isinstance(body, str):
        text = body
    else:
        text = "\n".join(body).rstrip()

    # textwrap merges paragraphs, ARGH
    # step 1: remove trailing whitespace from individual lines
    #   (this means that empty lines will just have \n, no invisible whitespace)
    lines = []
    for line in text.split("\n"):
        lines.append(line.rstrip())
    text = "\n".join(lines)
    paragraphs = text.split("\n\n")
    paragraphs2 = []
    kwargs = {}
    if subsequent_indent:
        kwargs['subsequent_indent'] = subsequent_indent
    for paragraph in paragraphs:
        paragraphs2.append("\n".join(textwrap.wrap(paragraph.strip(), width=76, **kwargs)).rstrip())
        if subsequent_indent:
            kwargs['initial_indent'] = subsequent_indent
    text = "\n\n".join(paragraphs2).rstrip()
    if not text.endswith("\n"):
        text += "\n"
    return text


def current_date():
    return time.strftime("%Y-%m-%d", time.localtime())

def sortable_datetime():
    return time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())


def prompt(prompt):
    return input("[{}> ".format(prompt))

def require_ok(prompt):
    prompt = "[{}> ".format(prompt)
    while True:
        s = input(prompt).strip()
        if s == 'ok':
            return s

class pushd:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.previous_cwd = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, *args):
        os.chdir(self.previous_cwd)


def safe_mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def which(cmd, path="PATH"):
    """Find cmd on PATH."""
    if os.path.exists(cmd):
        return cmd
    if cmd[0] == '/':
        return None
    for segment in os.getenv(path).split(":"):
        program = os.path.normpath(os.path.join(segment, cmd))
        if os.path.exists(program):
            return program
    return None


def strip_whitespace_lines(lines):
    # strip from head
    while lines:
        if lines[0]:
            break
        lines.pop(0)

    # strip from tail
    while lines:
        if lines[-1]:
            return
        lines.pop()


def longest_line(lines):
    longest = 0
    for line in lines:
        longest = max(longest, len(line))
    return longest


def version_key(element):
    fields = list(element.split("."))
    if len(fields) == 1:
        return element

    # in sorted order,
    # 3.5.0a1 < 3.5.0b1 < 3.5.0rc1 < 3.5.0
    # so for sorting purposes we transform
    # "3.5." and "3.5.0" into "3.5.0zz0"
    last = fields.pop()
    for s in ("a", "b", "rc"):
        if s in last:
            last, stage, stage_version = last.partition(s)
            break
    else:
        stage = 'zz'
        stage_version = "0"

    fields.append(last)
    while len(fields) < 3:
        fields.append("0")

    fields.extend([stage, stage_version])
    fields = [s.rjust(6, "0") for s in fields]

    return ".".join(fields)


def nonceify(body):
    digest = hashlib.md5(body.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)[0:6].decode('ascii')


def glob_versions():
    with pushd("Misc/NEWS.d"):
        versions = []
        for wildcard in ("2.*.rst", "3.*.rst", "next"):
            files = [x.partition(".rst")[0] for x in glob.glob(wildcard)]
            versions.extend(files)
    xform = [version_key(x) for x in versions]
    xform.sort(reverse=True)
    versions = sorted(versions, key=version_key, reverse=True)
    return versions


def glob_blurbs(version):
    filenames = []
    base = os.path.join("Misc", "NEWS.d", version)
    if version != "next":
        wildcard = base + ".rst"
        filenames.extend(glob.glob(wildcard))
    else:
        for section in sections:
            wildcard = os.path.join(base, sanitize_section(section), "*.rst")
            entries = glob.glob(wildcard)
            entries.sort(reverse=True)
            deletables = [x for x in entries if x.endswith("/README.rst")]
            for filename in deletables:
                entries.remove(filename)
            filenames.extend(entries)
    return filenames


def printable_version(version):
    if version == "next":
        return version
    if "a" in version:
        return version.replace("a", " alpha ")
    if "b" in version:
        return version.replace("b", " beta ")
    if "rc" in version:
        return version.replace("rc", " release candidate ")
    return version + " final"


class BlurbError(RuntimeError):
    pass

"""

The format of a blurb file:

    ENTRY
    [ENTRY2
    ENTRY3
    ...]

In other words, you may have one or more ENTRYs (entries) in a blurb file.

The format of an ENTRY:

    METADATA
    BODY

The METADATA section is optional.
The BODY section is mandatory and must be non-empty.

Format of the METADATA section:

  * Lines starting with ".." are metadata lines of the format:
        .. name: value
  * Lines starting with "#" are comments:
        # comment line
  * Empty and whitespace-only lines are ignored.
  * Trailing whitespace is removed.  Leading whitespace is not removed
    or ignored.

The first nonblank line that doesn't start with ".." or "#" automatically
terminates the METADATA section and is the first line of the BODY.

Format of the BODY section:

  * The BODY section should be a single paragraph of English text
    in ReST format.  It should not use the following ReST markup
    features:
      * section headers
      * comments
      * directives, citations, or footnotes
      * Any features that require significant line breaks,
        like lists, definition lists, quoted paragraphs, line blocks,
        literal code blocks, and tables.
    Note that this is not (currently) enforced.
  * Trailing whitespace is stripped.  Leading whitespace is preserved.
  * Empty lines between non-empty lines are preserved.
    Trailing empty lines are stripped.
  * The BODY mustn't start with "Issue #", "bpo-", or "- ".
    (This formatting will be inserted when rendering the final output.)
  * Lines longer than 76 characters will be wordwrapped.
      * In the final output, the first line will have
        "- bpo-<bpo-number>: " inserted at the front,
        and subsequent lines will have two spaces inserted
        at the front.

To terminate an ENTRY, specify a line containing only "..".  End of file
also terminates the last ENTRY.

-----------------------------------------------------------------------------

The format of a "next" file is exactly the same, except that we're storing
four pieces of metadata in the filename instead of in the metadata section.
Those four pieces of metadata are: section, bpo, date, and nonce.

-----------------------------------------------------------------------------

In addition to the four conventional metadata (section, bpo, date, and nonce),
there are two additional metadata used per-version: "release date" and
"no changes".  These may only be present in the metadata block in the *first*
blurb in a blurb file.
  * "release date" is the day a particular version of Python was released.
  * "no changes", if present, notes that there were no actual changes
    for this version.  When used, there are two more things that must be
    true about the the blurb file:
      * There should only be one entry inside the blurb file.
      * That entry's bpo number must be 0.

"""

class Blurbs(list):

    def parse(self, text, *, metadata=None, filename="input"):
        """
        Parses a string.  Appends a list of blurb ENTRIES to self, as tuples:
          (metadata, body)
        metadata is a dict.  body is a string.
        """

        metadata = metadata or {}
        body = []
        in_metadata = True

        line_number = None

        def throw(s):
            raise BlurbError("Error in {}:{}:\n{}".format(filename, line_number, s))

        def finish_entry():
            nonlocal body
            nonlocal in_metadata
            nonlocal metadata
            nonlocal self

            if not body:
                throw("Blurb 'body' text must not be empty!")
            text = textwrap_body(body)
            for naughty_prefix in ("- ", "Issue #", "bpo-"):
                if text.startswith(naughty_prefix):
                    throw("Blurb 'body' can't start with " + repr(naughty_prefix) + "!")

            no_changes = metadata.get('no changes')
            section = metadata.get('section')

            if not no_changes:
                if not section:
                    throw("No 'section' specified.  You must provide one!")
                elif section not in sections:
                    throw("Invalid 'section'!  You must use one of the predefined sections.")

            bpo = None
            try:
                bpo = int(metadata.get('bpo'))
            except (TypeError, ValueError):
                throw("Invalid bpo issue number! (" + repr(bpo) + ")")

            self.append((metadata, text))
            metadata = {}
            body = []
            in_metadata = True

        for line_number, line in enumerate(text.split("\n")):
            line = line.rstrip()
            if in_metadata:
                if line.startswith('..'):
                    line = line[2:].strip()
                    name, colon, value = line.partition(":")
                    assert colon
                    name = name.strip()
                    value = value.strip()
                    if name in metadata:
                        throw("Blurb metadata sets " + repr(name) + " twice!")
                    metadata[name] = value
                    continue
                if line.startswith("#") or not line:
                    continue
                in_metadata = False

            if line == "..":
                finish_entry()
                continue
            body.append(line)

        finish_entry()

    def load(self, filename, *, metadata=None):
        """
Read a blurb file.

Broadly equivalent to blurb.parse(open(filename).read()).
        """
        with open(filename, "rt", encoding="utf-8") as f:
            text = f.read()
        self.parse(text, metadata=metadata, filename=filename)

    def __str__(self):
        output = []
        add = output.append
        add_separator = False
        for metadata, body in self:
            if add_separator:
                add("\n..\n\n")
            else:
                add_separator = True
            if metadata:
                for name, value in sorted(metadata.items()):
                    add(".. {}: {}\n".format(name, value))
                add("\n")
            add(textwrap_body(body))
        return "".join(output)

    def save(self, path):
        dirname = os.path.dirname(path)
        safe_mkdir(dirname)

        text = str(self)
        with open(path, "wt", encoding="utf-8") as f:
            f.write(text)

    @staticmethod
    def _parse_next_filename(filename):
        """
Parses a "next" filename into its equivalent blurb metadata.
Returns a dict.
        """
        components = filename.split("/")
        section, filename = components[-2:]
        section = unsanitize_section(section)
        assert section in sections, "Unknown section {}".format(section)

        fields = [x.strip() for x in filename.split(".")]
        assert len(fields) >= 4, "Can't parse 'next' filename! filename {!r} fields {}".format(filename, fields)
        assert fields[-1] == "rst"

        metadata = {"date": fields[0], "nonce": fields[-2], "section": section}

        for field in fields[1:-2]:
            for name in ("bpo",):
                _, got, value = field.partition(name + "-")
                if got:
                    metadata[name] = value.strip()
                    break
            else:
                assert False, "Found unparsable field in 'next' filename: " + repr(field)

        return metadata

    def load_next(self, filename):
        metadata = self._parse_next_filename(filename)
        o = type(self)()
        o.load(filename, metadata=metadata)
        assert len(o) == 1
        self.extend(o)

    def ensure_metadata(self):
        metadata, body = self[-1]
        assert 'section' in metadata
        for name, default in (
            ("bpo", "0"),
            ("date", sortable_datetime()),
            ("nonce", nonceify(body)),
            ):
            if name not in metadata:
                metadata[name] = default

    def _extract_next_filename(self):
        """
        changes metadata!
        """
        self.ensure_metadata()
        metadata, body = self[-1]
        metadata['section'] = sanitize_section(metadata['section'])
        metadata['root'] = root
        path = "{root}/Misc/NEWS.d/next/{section}/{date}.bpo-{bpo}.{nonce}.rst".format_map(metadata)
        for name in "root section date bpo nonce".split():
            del metadata[name]
        return path


    def save_next(self):
        assert len(self) == 1
        blurb = type(self)()
        metadata, body = self[0]
        metadata = dict(metadata)
        blurb.append((metadata, body))
        filename = blurb._extract_next_filename()
        blurb.save(filename)
        return filename

    def save_split_next(self):
        """
        Save out blurbs created from "blurb split".
        They don't have dates, so we have to get creative.
        """
        filenames = []
        # the "date" MUST have a leading zero.
        # this ensures these files sort after all
        # newly created blurbs.
        width = int(math.ceil(math.log(len(self), 10))) + 1
        i = 1
        blurb = Blurbs()
        while self:
            metadata, body = self.pop()
            metadata['date'] = str(i).rjust(width, '0')
            if 'release date' in metadata:
                del metadata['release date']
            blurb.append((metadata, body))
            filename = blurb._extract_next_filename()
            blurb.save(filename)
            blurb.clear()
            filenames.append(filename)
            i += 1
        return filenames


tests_run = 0

class TestParserPasses(unittest.TestCase):
    directory = "tests/pass"

    def filename_test(self, filename):
        b = Blurbs()
        b.load(filename)
        self.assertTrue(b)

    def test_files(self):
        global tests_run
        with pushd(self.directory):
            for filename in glob.glob("*"):
                self.filename_test(filename)
                print(".", end="")
                sys.stdout.flush()
                tests_run += 1


class TestParserFailures(TestParserPasses):
    directory = "tests/fail"

    def filename_test(self, filename):
        b = Blurbs()
        with self.assertRaises(Exception):
            b.read(filename)



def run(s):
    process = subprocess.run(s.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.check_returncode()
    return process.stdout.decode('ascii')


readme_re = re.compile(r"This is Python version [23]\.\d")

def chdir_to_repo_root():
    global root

    def fail(where):
        sys.exit('You\'re not inside a CPython repo right now! (failed at "{}")'.format(where))

    try:
        git_dir = run("git rev-parse --git-dir").strip()
    except subprocess.CalledProcessError:
        fail("git rev-parse")

    if '.git/worktrees' in git_dir:
        with open(os.path.join(git_dir, 'gitdir'), "rt", encoding="utf-8") as f:
            git_dir = f.read().strip()
    root = os.path.dirname(os.path.abspath(git_dir))
    os.chdir(root)

    # make totally, absolutely sure we're in a valid CPython repo
    def test_first_line(filename, test):
        with open(filename, "rt") as f:
            lines = f.read().split('\n')
            if not (lines and test(lines[0])):
                fail(filename)

    for readme in ("README", "README.rst"):
        if os.path.exists(readme):
            test_first_line(readme, readme_re.match)
            break
    else:
        fail(readme)

    test_first_line("LICENSE",  "A. HISTORY OF THE SOFTWARE".__eq__)

    def test_existence(filename):
        if not os.path.exists(filename):
            fail(filename)
        
    test_existence("Include/Python.h")
    test_existence("Python/ceval.c")

    return root


def error(*a):
    s = " ".join(str(x) for x in a)
    sys.exit("Error: " + s)


subcommands = {}

def subcommand(fn):
    global subcommands
    name = fn.__name__
    subcommands[name] = fn
    return fn

def get_subcommand(subcommand):
    fn = subcommands.get(subcommand)
    if not fn:
        error("Unknown subcommand: {}".format(subcommand))
    return fn



@subcommand
def help(subcommand=None):
    """
Print help for subcommands.

Prints the help text for the specified subcommand.
If subcommand is not specified, prints one-line summaries for every command.
    """

    if not subcommand:
        print("blurb [subcommand] [options...]")
        print()
        print("Management tool for CPython Misc/NEWS and Misc/NEWS.d entries.")
        print()

        # print list of subcommands
        summaries = []
        longest_name_len = -1
        for name, fn in subcommands.items():
            longest_name_len = max(longest_name_len, len(name))
            if not fn.__doc__:
                error("help is broken, no docstring for " + fn.__name__)
            fields = fn.__doc__.lstrip().split("\n")
            if not fields:
                first_line = "(no help available)"
            else:
                first_line = fields[0]
            summaries.append((name, first_line))
        summaries.sort()

        print("Available subcommands:")
        print()
        for name, summary in summaries:
            print(" ", name.ljust(longest_name_len), " ", summary)

        print()
        print("If blurb is run without any arguments, this is equivalent to 'blurb add'.")

        sys.exit(0)

    fn = get_subcommand(subcommand)
    doc = fn.__doc__.strip()
    if not doc:
        error("help is broken, no docstring for " + subcommand)

    options = []
    positionals = []

    nesting = 0
    for name, p in inspect.signature(fn).parameters.items():
        if p.kind == inspect.Parameter.KEYWORD_ONLY:
            short_option = name[0]
            options.append(" [-{}|--{}]".format(short_option, name))
        elif p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            positionals.append(" ")
            has_default = (p.default != inspect._empty)
            if has_default:
                positionals.append("[")
                nesting += 1
            positionals.append("<{}>".format(name))
    positionals.append("]" * nesting)


    parameters = "".join(options + positionals)
    print("blurb {}{}".format(subcommand, parameters))
    print()
    print(doc)
    sys.exit(0)


@subcommand
def test(*args):
    """
Run unit tests.  Only works inside source repo, not when installed.
    """
    # unittest.main doesn't work because this isn't a module
    # so we'll do it ourselves

    print("-" * 79)

    for clsname, cls in sorted(globals().items()):
        if clsname.startswith("Test") and isinstance(cls, type):
            o = cls()
            for fnname in sorted(dir(o)):
                if fnname.startswith("test"):
                    fn = getattr(o, fnname)
                    if callable(fn):
                        fn()
    print()
    print(tests_run, "tests passed.")


def find_editor():
    for var in 'GIT_EDITOR', 'EDITOR':
        editor = os.environ.get(var)
        if editor is not None:
            return editor
    if sys.platform == 'win32':
        fallbacks = ['notepad.exe']
    else:
        fallbacks = ['/etc/alternatives/editor', 'nano']
    for fallback in fallbacks:
        if os.path.isabs(fallback):
            found_path = fallback
        else:
            found_path = shutil.which(fallback)
        if found_path and os.path.exists(found_path):
            return found_path
    error('Could not find an editor! Set the EDITOR environment variable.')


@subcommand
def add():
    """
Add a blurb (a Misc/NEWS entry) to the current CPython repo.
    """

    editor_command = shlex.split(find_editor(), posix=os.name == 'posix')

    handle, tmp_path = tempfile.mkstemp(".rst")
    os.close(handle)
    atexit.register(lambda : os.unlink(tmp_path))
    editor_command.append(tmp_path)

    def init_tmp_with_template():
        with open(tmp_path, "wt", encoding="utf-8") as f:
            # hack:
            # my editor likes to strip trailing whitespace from lines.
            # normally this is a good idea.  but in the case of the template
            # it's unhelpful.
            # so, manually ensure there's a space at the end of the bpo line.
            text = template

            bpo_line = ".. bpo:"
            without_space = "\n" + bpo_line + "\n"
            with_space = "\n" + bpo_line + " \n"
            if without_space not in text:
                sys.exit("Can't find BPO line to ensure there's a space on the end!")
            text = text.replace(without_space, with_space)
            f.write(text)

    init_tmp_with_template()

    while True:
        subprocess.run(editor_command)

        failure = None
        blurb = Blurbs()
        try:
            blurb.load(tmp_path)
        except BlurbError as e:
            failure = str(e)

        if not failure:
            assert len(blurb) # if parse_blurb succeeds, we should always have a body
            if len(blurb) > 1:
                failure = "Too many entries!  Don't specify '..' on a line by itself."

        if failure:
            print()
            print("Error: {}".format(failure))
            print()
            try:
                prompt("Hit return to retry (or Ctrl-C to abort)")
            except KeyboardInterrupt:
                print()
                return
            print()
            continue
        break

    path = blurb.save_next()
    git_add_files.append(path)
    flush_git_add_files()
    print("Ready for commit.")



@subcommand
def release(version):
    """
Move all new blurbs to a single blurb file for the release.

This is used by the release manager when cutting a new release.
    """
    if version == ".":
        # harvest version number from dirname of repo
        # I remind you, we're in the Misc subdir right now
        version = os.path.basename(os.path.dirname(os.getcwd()))

    existing_filenames = glob_blurbs(version)
    if existing_filenames:
        error("Sorry, can't handle appending 'next' files to an existing version (yet).")

    output = "Misc/NEWS.d/{}.rst".format(version)
    filenames = glob_blurbs("next")
    blurbs = Blurbs()
    date = current_date()

    if not filenames:
        print("No blurbs found.  Setting {} as having no changes.".format(version))
        body = "There were no new changes in version {}.\n".format(version)
        metadata = {"no changes": "True", "bpo": "0", "section": "Library", "date": date, "nonce": nonceify(body)}
        blurbs.append((metadata, body))
    else:
        no_changes = None
        count = len(filenames)
        print('Merging {} blurbs to "{}".'.format(count, output))

        for filename in filenames:
            if not filename.endswith(".rst"):
                continue
            blurbs.load_next(filename)

        metadata = blurbs[0][0]

    metadata['release date'] = date
    print("Saving.")

    blurbs.save(output)
    git_add_files.append(output)
    flush_git_add_files()

    # sanity check: ensuring that saving/reloading the merged blurb file works.
    blurbs2 = Blurbs()
    blurbs2.load(output)
    assert blurbs2 == blurbs, "Reloading {} isn't reproducable?!".format(output)

    print("Removing {} 'next' files from git.".format(len(filenames)))
    git_rm_files.extend(filenames)
    flush_git_rm_files()

    print()
    print("Ready for commit.")



@subcommand
def merge(output=None, *, forced=False):
    """
Merge all blurbs together into a single Misc/NEWS file.

Optional output argument specifies where to write to.
Default is <cpython-root>/Misc/NEWS.

If overwriting, blurb merge will prompt you to make sure it's okay.
To force it to overwrite, use -f.
    """
    if output:
        output = os.path.join(original_dir, output)
    else:
        output = "Misc/NEWS"

    versions = glob_versions()
    if not versions:
        sys.exit("You literally don't have ANY blurbs to merge together!")

    if os.path.exists(output) and not forced:
        builtins.print("You already have a", repr(output), "file.")
        require_ok("Type ok to overwrite")

    news = open(output, "wt", encoding="utf-8")

    def print(*a, sep=" "):
        s = sep.join(str(x) for x in a)
        return builtins.print(s, file=news)

    print ("""
+++++++++++
Python News
+++++++++++

""".strip())

    for version in versions:
        filenames = glob_blurbs(version)

        blurbs = Blurbs()
        if version == "next":
            for filename in filenames:
                if os.path.basename(filename) == "README.rst":
                    continue
                blurbs.load_next(filename)
            if not blurbs:
                continue
            metadata = blurbs[0][0]
            metadata['release date'] = "XXXX-XX-XX"
        else:
            assert len(filenames) == 1
            blurbs.load(filenames[0])

        header = "What's New in Python " + printable_version(version) + "?"
        print()
        print(header)
        print("=" * len(header))
        print()


        metadata, body = blurbs[0]
        release_date = metadata["release date"]

        print("*Release date: {}*".format(release_date))
        print()

        if "no changes" in metadata:
            print(body)
            print()
            continue

        last_section = None
        for metadata, body in blurbs:
            section = metadata['section']
            if last_section != section:
                last_section = section
                print(section)
                print("-" * len(section))
                print()

            bpo = metadata['bpo']
            if int(bpo):
                body = "bpo-" + bpo + ": " + body
            body = "- " + body
            text = textwrap_body(body, subsequent_indent='  ')
            print(text)
    print()
    print("**(For information about older versions, consult the HISTORY file.)**")
    news.close()


git_add_files = []
def flush_git_add_files():
    if git_add_files:
        subprocess.run(["git", "add", *git_add_files], stdout=subprocess.PIPE, stderr=subprocess.PIPE).check_returncode()
        git_add_files.clear()

git_rm_files = []
def flush_git_rm_files():
    if git_rm_files:
        try:
            subprocess.run(["git", "rm", "-f", *git_rm_files], stdout=subprocess.PIPE, stderr=subprocess.PIPE).check_returncode()
        except subprocess.CalledProcessError:
            pass

        # clean up
        for path in git_rm_files:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

        git_rm_files.clear()


# @subcommand
# def noop():
#     "Do-nothing command.  Used for blurb smoke-testing."
#     pass


@subcommand
def populate():
    """
Creates and populates the Misc/NEWS.d directory tree.
    """
    os.chdir("Misc")
    safe_mkdir("NEWS.d/next")

    for section in sections:
        dir_name = sanitize_section(section)
        dir_path = "NEWS.d/next/{}".format(dir_name)
        safe_mkdir(dir_path)
        readme_path = "NEWS.d/next/{}/README.rst".format(dir_name)
        with open(readme_path, "wt", encoding="utf-8") as f:
            f.write("Put news entry ``blurb`` files for the *{}* section in this directory.\n".format(section))
        git_add_files.append(dir_path)
        git_add_files.append(readme_path)
    flush_git_add_files()


# @subcommand
# def arg(*, boolean=False, option=True):
#    """
#    Test function for blurb command-line processing.
#    """
#    print("arg: boolean {} option {}".format(boolean, option))


@subcommand
def split(*, released=False):
    """
Split the current Misc/NEWS into a zillion little blurb files.

Assumes that the newest version section in Misc/NEWS is under
development, and splits those entries into the "next" subdirectory.
If the current version has actually been released, use the
--released flag.

Also runs "blurb populate" for you.
    """

    # note: populate also does chdir $python_root/Misc for you
    populate()

    if not os.path.isfile("NEWS"):
        error("You don't have a Misc/NEWS file!")

    def global_sections():
        global sections
        return sections

    sections = set(global_sections())
    release_date_marker = "Release date:"
    whats_new_marker = "What's New in Python "

    blurbs = Blurbs()

    accumulator = []
    bpo = "0"
    serial_number = 9999
    version = None
    release_date = None
    section = None
    see_also = None
    no_changes = None
    security = None
    blurb_count = 0
    version_count = 0


    def flush_blurb():
        nonlocal accumulator
        nonlocal serial_number
        nonlocal bpo
        nonlocal release_date
        nonlocal see_also
        nonlocal no_changes
        nonlocal blurb_count
        nonlocal security

        if accumulator:
            if version:
                # strip trailing blank lines
                while accumulator:
                    line = accumulator.pop()
                    if not line.rstrip():
                        continue
                    accumulator.append(line)
                    break
                if see_also:
                    fields = []
                    see_also = see_also.replace(" and ", ",")
                    for field in see_also.split(","):
                        field = field.strip()
                        if not field:
                            continue
                        if field.startswith("and "):
                            field = field[5:].lstrip()
                        if field.lower().startswith("issue"):
                            field = field[5:].strip()
                        if field.startswith("#"):
                            field = field[1:]
                        try:
                            int(field)
                            field = "bpo-" + field
                        except ValueError:
                            pass
                        fields.append(field)
                    see_also = ", ".join(fields)
                    # print("see_also: ", repr(see_also))
                    accumulator.append("(See also: {})".format(see_also))
                    see_also = None
                if not accumulator:
                    return
                if not (section or no_changes):
                    error("No section for line " + str(line_number) + "!")

                body = "\n".join(accumulator) + "\n"
                metadata = {}
                metadata["bpo"] = bpo
                metadata["date"] = str(serial_number)
                if section:
                    metadata["section"] = section
                else:
                    assert no_changes
                metadata["nonce"] = nonceify(body)
                if security:
                    # retroactively change section to "Security"
                    assert section
                    metadata["original section"] = metadata["section"]
                    metadata["section"] = "Security"

                if release_date is not None:
                    assert not len(blurbs)
                    metadata["release date"] = release_date
                    release_date = None
                if no_changes is not None:
                    assert not len(blurbs)
                    metadata["no changes"] = "True"
                    no_changes = None
                blurbs.append((metadata, body))
                blurb_count += 1

            bpo = "0"
            serial_number -= 1
            accumulator.clear()

    def flush_version():
        global git_add_files
        nonlocal released
        nonlocal version_count

        flush_blurb()
        if version is None:
            assert not blurbs, "version should only be None initially, we shouldn't have blurbs yet"
            return
        assert blurbs, "No blurbs defined when flushing version {}!".format(version)
        output = "NEWS.d/{}.rst".format(version)

        if released:
            # saving merged blurb file for version, e.g. Misc/NEWS.d/3.7.0a1.rst
            blurbs.save(output)
            git_add_files.append(output)
        else:
            # saving a million old-school blurb next files
            # with serial numbers instead of dates
            # e.g. Misc/NEWS.d/next/IDLE/094.bpo-25514.882pXa.rst
            filenames = blurbs.save_split_next()
            git_add_files.extend(filenames)
            released = True
        blurbs.clear()
        version_count += 1

    with open("NEWS", "rt", encoding="utf-8") as f:
        for line_number, line in enumerate(f):
            line = line.rstrip()

            if line.startswith("\ufeff"):
                line = line[1:]

            # clean the slightly dirty data:
            # 1. inconsistent names for sections, etc
            for old, new in (
                ("C-API", "C API"),
                ("Core and builtins", "Core and Builtins"),
                ("Tools", "Tools/Demos"),
                ("Tools / Demos", "Tools/Demos"),
                ("Misc", "Windows"), # only used twice, both were really Windows
                ("Mac", "macOS"),
                ("Mac OS X", "macOS"),
                ("Extension Modules", "Library"),
                ("Whats' New in Python 2.7.6?", "What's New in Python 2.7.6?"),
                ):
                if line == old:
                    line = new
            # 2. unusual indenting
            _line = line.lstrip()
            if _line.startswith(("- Issue #", "- bpo-")):
                line = _line
            if _line == ".characters() and ignorableWhitespace() methods.  Original patch by Sebastian":
                line = " " + line
            # 3. fix version for What's New
            if line.startswith(whats_new_marker):
                flush_version()
                version = line[len(whats_new_marker):].strip().lower()
                for old, new in (
                    ("?", ""),
                    (" alpha ", "a"),
                    (" beta ", "b"),
                    (" release candidate ", "rc"),
                    (" final", ""),
                    ("3.5a", "3.5.0a"),
                    ):
                    version = version.replace(old, new)
                section = None
                continue
            # 3.a. fix specific precious little snowflakes
            # who can't be bothered to follow our stifling style conventions
            # and like, did their own *thing*, man.
            if line.startswith("- Issue #27181 remove statistics.geometric_mean"):
                line = line.replace(" remove", ": remove")
            elif line.startswith("* bpo-30357: test_thread: setUp()"):
                line = line.replace("* bpo-30357", "- bpo-30357")
            elif line.startswith("- Issue #25262. Added support for BINBYTES8"):
                line = line.replace("#25262.", "#25262:")
            elif line.startswith("- Issue #21032. Fixed socket leak if"):
                line = line.replace("#21032.", "#21032:")
            elif line.startswith("- Issue ##665194: Update "):
                line = line.replace("##665194", "#665194")
            elif line.startswith("- Issue #13449 sched.scheduler.run()"):
                line = line.replace("#13449 sched", "#13449: sched")
            elif line.startswith("- Issue #8684 sched.scheduler class"):
                line = line.replace("#8684 sched", "#8684: sched")
            elif line.startswith(" bpo-29243: Prevent unnecessary rebuilding"):
                line = line.replace(" bpo-29243:", "- bpo-29243:")
            elif line.startswith((
                "- Issue #11603 (again): Setting",
                "- Issue #15801 (again): With string",
                )):
                line = line.replace(" (again):", ":")
            elif line.startswith("- Issue #1665206 (partially): "):
                line = line.replace(" (partially):", ":")
            elif line.startswith("- Issue #2885 (partial): The"):
                line = line.replace(" (partial):", ":")
            elif line.startswith("- Issue #2885 (partial): The"):
                line = line.replace(" (partial):", ":")
            elif line.startswith("- Issue #1797 (partial fix):"):
                line = line.replace(" (partial fix):", ":")
            elif line.startswith("- Issue #5828 (Invalid behavior of unicode.lower): Fixed bogus logic in"):
                line = line.replace(" (Invalid behavior of unicode.lower):", ":")
            elif line.startswith("- Issue #4512 (part 2): Promote ``ZipImporter._get_filename()`` to be a public"):
                line = line.replace(" (part 2):", ":")
            elif line.startswith("- Revert bpo-26293 for zipfile breakage. See also bpo-29094."):
                line = "- bpo-26293, bpo-29094: Change resulted because of zipfile breakage."
            elif line.startswith("- Revert a37cc3d926ec (Issue #5322)."):
                line = "- Issue #5322: Revert a37cc3d926ec."
            elif line.startswith("- Patch #1970 by Antoine Pitrou: Speedup unicode whitespace and"):
                line = "- Issue #1970: Speedup unicode whitespace and"
            elif line.startswith("  linebreak detection"):
                line = "  linebreak detection.  (Patch by Antoine Pitrou.)"
            elif line.startswith("- Patch #1182394 from Shane Holloway: speed up HMAC.hexdigest."):
                line = "- Issue #1182394: Speed up ``HMAC.hexdigest``.  (Patch by Shane Holloway.)"
            elif line.startswith("- Variant of patch #697613: don't exit the interpreter on a SystemExit"):
                line = "- Issue #697613: Don't exit the interpreter on a SystemExit"
            elif line.startswith("- Bugs #1668596/#1720897: distutils now copies data files even if"):
                line = "- Issue #1668596, #1720897: distutils now copies data files even if"
            elif line.startswith("- Reverted patch #1504333 to sgmllib because it introduced an infinite"):
                line = "- Issue #1504333: Reverted change to sgmllib because it introduced an infinite"
            elif line.startswith("- PEP 465 and Issue #21176: Add the '@' operator for matrix multiplication."):
                line = "- Issue #21176: PEP 465: Add the '@' operator for matrix multiplication."
            elif line.startswith("- Issue: #15138: base64.urlsafe_{en,de}code() are now 3-4x faster."):
                line = "- Issue #15138: base64.urlsafe_{en,de}code() are now 3-4x faster."
            elif line.title().startswith(("- Request #", "- Bug #", "- Patch #", "- Patches #")):
                # print("FIXING LINE {}: {!r}".format(line_number), line)
                line = "- Issue #" + line.partition('#')[2]
                # print("FIXED LINE {!r}".format(line))
            # else:
            #     print("NOT FIXING LINE {}: {!r}".format(line_number, line))


            # 4. determine the actual content of the line

            # 4.1 section declaration
            if line in sections:
                flush_blurb()
                section = line
                continue

            # 4.2 heading ReST marker
            if line.startswith((
                "===",
                "---",
                "---",
                "+++",
                "Python News",
                "**(For information about older versions, consult the HISTORY file.)**",
                )):
                continue

            # 4.3 version release date declaration
            if line.startswith(release_date_marker) or (
                line.startswith("*") and release_date_marker in line):
                while line.startswith("*"):
                    line = line[1:]
                while line.endswith("*"):
                    line = line[:-1]
                release_date = line[len(release_date_marker):].strip()
                continue

            # 4.4 no changes declaration
            if line.strip() in (
                '- No changes since release candidate 2',
                'No changes from release candidate 2.',
                'There were no code changes between 3.5.3rc1 and 3.5.3 final.',
                'There were no changes between 3.4.6rc1 and 3.4.6 final.',
                ):
                no_changes = True
                if line.startswith("- "):
                    line = line[2:]
                accumulator.append(line)
                continue

            # 4.5 start of new blurb
            if line.startswith("- "):
                flush_blurb()
                line = line[2:]
                security = line.startswith("[Security]")
                if security:
                    line = line[10:].lstrip()

                if line.startswith("Issue"):
                    line = line[5:].lstrip()
                    if line.startswith("s"):
                        line = line[1:]
                    line = line.lstrip()
                    if line.startswith("#"):
                        line = line[1:].lstrip()
                    parse_bpo = True
                elif line.startswith("bpo-"):
                    line = line[4:]
                    parse_bpo = True
                else:
                    # print("[[{:8} no bpo]] {}".format(line_number, line))
                    parse_bpo = False
                if parse_bpo:
                    # GAAAH
                    if line == "17500, and https://github.com/python/pythondotorg/issues/945: Remove":
                        line = "Remove"
                        bpo = "17500"
                        see_also = "https://github.com/python/pythondotorg/issues/945"
                    else:
                        bpo, colon, line = line.partition(":")
                        line = line.lstrip()
                        bpo, comma, see_also = bpo.partition(",")
                        if comma:
                            see_also = see_also.strip()
                            # if it's just an integer, add bpo- to the front
                            try:
                                int(see_also)
                                see_also = "bpo-" + see_also
                            except ValueError:
                                pass
                        else:
                            # - Issue #21529 (CVE-2014-4616)
                            bpo, space_paren, see_also = bpo.partition(" (")
                            if space_paren:
                                see_also = see_also.rstrip(")")
                            else:
                                # - Issue #19544 and Issue #1180:
                                bpo, space_and, see_also = bpo.partition(" and ")
                                if not space_and:
                                    bpo, space_and, see_also = bpo.partition(" & ")
                                if space_and:
                                    see_also = see_also.replace("Issue #", "bpo-").strip()
                                else:
                                    # - Issue #5258/#10642: if site.py
                                    bpo, slash, see_also = bpo.partition("/")
                                    if space_and:
                                        see_also = see_also.replace("#", "bpo-").strip()
                    try:
                        int(bpo) # this will throw if it's not a legal int
                    except ValueError:
                        sys.exit("Couldn't convert bpo number to int on line {}! ".format(line_number) + repr(bpo))
                    if see_also == "partially":
                        sys.exit("What the hell on line {}! ".format(line_number) + repr(bpo))

            # 4.6.1 continuation of blurb
            elif line.startswith("  "):
                line = line[2:]
            # 4.6.2 continuation of blurb
            elif line.startswith(" * "):
                line = line[3:]
            elif line:
                sys.exit("Didn't recognize line {}! ".format(line_number) + repr(line))
            # only add blank lines if we have an initial line in the accumulator
            if line or accumulator:
                accumulator.append(line)

    flush_version()

    assert git_add_files
    flush_git_add_files()
    git_rm_files.append("NEWS")
    flush_git_rm_files()

    print("Wrote {} news items across {} versions.".format(blurb_count, version_count))
    print()
    print("Ready for commit.")



def main():
    global original_dir

    args = sys.argv[1:]

    if not args:
        args = ["add"]
    elif args[0] == "-h":
        # slight hack
        args[0] = "help"

    subcommand = args[0]
    args = args[1:]

    fn = get_subcommand(subcommand)

    # hack
    if fn in (test, help):
        sys.exit(fn(*args))

    try:
        original_dir = os.getcwd()
        chdir_to_repo_root()

        # map keyword arguments to options
        # we only handle boolean options
        # and they must have default values
        short_options = {}
        long_options = {}
        kwargs = {}
        for name, p in inspect.signature(fn).parameters.items():
            if p.kind == inspect.Parameter.KEYWORD_ONLY:
                assert isinstance(p.default, bool), "blurb command-line processing only handles boolean options"
                kwargs[name] = p.default
                short_options[name[0]] = name
                long_options[name] = name

        filtered_args = []
        done_with_options = False

        def handle_option(s, dict):
            name = dict.get(s, None)
            if not name:
                sys.exit('blurb: Unknown option for {}: "{}"'.format(subcommand, s))
            kwargs[name] = not kwargs[name]

        # print("short_options {} long_options {}".format(short_options, long_options))
        for a in args:
            if done_with_options:
                filtered_args.append(a)
                continue
            if a.startswith('-'):
                if a == "--":
                    done_with_options = True
                elif a.startswith("--"):
                    handle_option(a[2:], long_options)
                else:
                    for s in a[1:]:
                        handle_option(s, short_options)
                continue
            filtered_args.append(a)


        sys.exit(fn(*filtered_args, **kwargs))
    except TypeError as e:
        # almost certainly wrong number of arguments.
        # count arguments of function and print appropriate error message.
        specified = len(args)
        required = optional = 0
        for p in inspect.signature(fn).parameters.values():
            if p.default == inspect._empty:
                required += 1
            else:
                optional += 1
        total = required + optional

        if required <= specified <= total:
            # whoops, must be a real type error, reraise
            raise e

        how_many = "{} argument".format(specified)
        if specified != 1:
            how_many += "s"

        if total == 0:
            middle = "accepts no arguments"
        else:
            if total == required:
                middle = "requires"
            else:
                plural = "" if required == 1 else "s"
                middle = "requires at least {} argument{} and at most".format(required, plural)
            middle += " {} argument".format(total)
            if total != 1:
                middle += "s"

        print('Error: Wrong number of arguments!\n\nblurb {} {},\nand you specified {}.'.format(subcommand, middle, how_many))
        print()
        print("usage: ", end="")
        help(subcommand)


if __name__ == '__main__':
    main()
