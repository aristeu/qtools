#!/bin/env python3
import sys
import os
import configparser
import git
import subprocess
import optparse
import re

CONFIG_DEFAULT = '~/.config/qtools/config'
DEFAULT_COMMIT_INTERVAL=600

# gets a list of patches in the same patchset by considering date and author
# FIXME this is also used in qimport, might move this later to a library
def list_patchset(repo, branch, interval, commit):
    author_email = commit.author.email
    date = commit.committed_date

    commit_list = []
    found_commit = False
    for c in repo.iter_commits(branch):
        if c.committed_date < (date - interval):
            # we're done looking
            break
        if c.committed_date < (date + interval):
            if c.hexsha == commit.hexsha:
                found_commit = True
            if c.author.email == author_email:
                commit_list.append(c.hexsha)
            else:
                if found_commit:
                    # we did it,
                    break
                # author might have changed and we didn't find the target commit
                commit_list.clear()

    if len(commit_list) == 0:
        sys.stderr.write("Commit %s not found in branch %s. Specify a different repo or branch\n" % (commit_sha, branch))
        sys.stderr.write("Until an option is implemented to do this automatically, run 'git branch -a --contains %s'\n" % commit_sha)
        return 1

    commit_list.reverse()
    return commit_list

def get_commit_sha(f):
    regex = re.compile('^commit ([a-f0-9]{40})')
    for l in f.readlines():
        res = regex.match(l)
        if res:
            return res.group(1)
    return None

def get_commit_list_from_series(patches_dir = "patches/"):
    output = []

    try:
        f = open("%s/series" % patches_dir, "r")
        series = []
        for patch in f.readlines():
            patch = patch.replace('\n', '')
            p = open("%s/%s" % (patches_dir, patch), "r")
            c = get_commit_sha(p)
            p.close()
            if c is not None:
                series.append(c)
        f.close()
        return series
    except Exception as error:
        raise Exception("Unable to open patch/series (%s)" % str(error))

# possible options:
# - patches/ location
# - linus repo
# - branch
# - period between patches to consider a different patchset
def main(argv):
    whole_list = []

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

    missing = []
    quilt_commits = get_commit_list_from_series()
    for c in quilt_commits:
        if c in whole_list:
            continue
        for p in list_patchset(repo, "master", DEFAULT_COMMIT_INTERVAL, repo.commit(c)):
            if p not in whole_list:
                whole_list.append(p)
            if p not in quilt_commits:
                if p not in missing:
                    # FIXME: might not be backported yet
                    missing.append(p)

    # keep missing in a list, we might turn this into a function
    for c in missing:
        print(c)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

