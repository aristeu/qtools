#!/bin/env python3
import sys
import os
import configparser
import git
import optparse
import datetime
import difflib

CONFIG_DEFAULT = '~/.config/qtools/config'
# we can add an option to specify branch and another to do it automatically (git branch -a --contains <sha>)
DEFAULT_BRANCH = 'master'

def save_backup(filename, s):
    d = datetime.datetime.now()
    backup = ".backup-%s" % d.strftime("%Y%m%d-%H%M%S")
    f = open(filename + backup, "w")
    f.write(s.read())
    f.close()

def main(argv):
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-a", "--apply", dest="do_apply", default=False, help="Apply changes instead of showing differences", action="store_true")
    parser.add_option("-f", "--force", dest="force", default=False, help="Ignore commits that won't be found and list them at the end", action="store_true")
    parser.add_option("-g", "--git", dest="git", default=None, help="Specify a different git repository path instead of the one in the configuration", metavar="GIT")
    parser.add_option("-b", "--branch", dest="branch", default=DEFAULT_BRANCH, help="Use branch BRANCH in the specified repository", metavar="BRANCH")
    (options, args) = parser.parse_args()

    path = options.git
    do_apply = options.do_apply
    branch = options.branch
    force = options.force

    if path is None:
        config = configparser.ConfigParser()
        try:
            config.read(os.path.expanduser(CONFIG_DEFAULT))
            if 'repository' not in config:
                sys.stderr.write("Repository section not found in the config file\n")
                return 1
            if 'path' not in config['repository']:
                sys.stderr.write("Repository section in the config file doesn't contain path=\n")
                return 1
            path = config['repository']['path']
        except:
            sys.stderr.write("Unable to read the config file, which is mandatory for now\n")
            return 1

    repo = git.Repo(path)
    try:
        repo = git.Repo(path)
    except:
        sys.stderr.write("Unable to open git repo at %s\n" % path)
        return 1

    try:
        series_file = open("patches/series", "r")
    except Exception as ex:
        raise("Unable to open series file (%s)" % str(ex))

    series_hash = []
    found = []
    missing = []
    series = series_file.readlines()
    series_newline = []
    for i,l in enumerate(series):
        if l.startswith('#'):
            continue
        series[i] = l.replace('\n', '')
        series_newline.append(l)
        series_hash.append(l.replace('.patch\n',''))

    for c in repo.iter_commits(branch):
        if c.hexsha in series_hash:
            found.append(c.hexsha)
        if len(found) == len(series):
            break

    for c in series_hash:
        if c not in found:
            missing.append(c)

    if not force:
        if len(series_hash) != len(found):
            sys.stderr.write("Not all commits were found (did you use the right branch?):\n")
            for c in missing:
                sys.stderr.write("%s.patch\n" % c)
            sys.stderr.write("Use -f to ignore these commits and run anyway. They'll be placed at the end of the series\n")
            return 1

    found.reverse()

    if do_apply:
        save_backup("patches/series", series_file)
        series_file.close()
        series_file = open("patches/series", "w")

        for c in found:
            series_file.write("%s.patch\n" % c)

        # we write the commits that weren't found (e.g. enable-config-foo.patch) at the end
        if (force):
            for c in missing:
                series_file.write("%s.patch\n" % c)
    else:
        # if we're forcing, the unknown patches are added to the end
        ordered = []
        for c in found + missing:
            ordered.append("%s.patch\n" % c)
        for line in difflib.unified_diff(series_newline, ordered, fromfile="local", tofile="upstream"):
            sys.stdout.write(line)

    series_file.close()

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))

