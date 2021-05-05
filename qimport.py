#!/bin/env python3
import sys
import os
import configparser
import git
import subprocess
import optparse

CONFIG_DEFAULT = '~/.config/qtools/config'
# We only look at patches committed within 10min of the target one
DEFAULT_COMMIT_INTERVAL=600
# we can add an option to specify branch and another to do it automatically (git branch -a --contains <sha>)
DEFAULT_BRANCH = 'master'

def write_single_patch(path, series, commit):
    patch = "%s.patch" % commit
    f = open("patches/%s" % patch, "w")
    # ugh. Couldn't make commit.diff work the same way
    formatted_patch = subprocess.check_output(["git", "-C", path, "log", "-p", "-1", commit])
    f.write(formatted_patch.decode('utf-8'))
    f.close()
    series.write("%s\n" % patch)

# gets a list of patches in the same patchset by considering date and author
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

def import_patches(repo, path, commit_list):
    try:
        os.mkdir("patches")
    except FileExistsError:
        pass
    except OSError as error:
        raise("Unable to create directory patches: %s\n" % str(error))

    mode = "r+"
    if not os.path.exists("patches/series"):
        mode = "w+"

    try:
        series = open("patches/series", mode)
    except Exception as ex:
        raise("Unable to open series file: %s\n" % str(ex))

    lines = series.readlines()
    for c in commit_list:
        commit = repo.commit(c)
        patch = "%s.patch" % c
        if ("%s\n" % patch) in lines:
            print("Skipping %s: already in series" % patch)
            continue
        write_single_patch(path, series, c)
    series.close()

def import_single_patch(repo, path, sha):
    commit_list = [ sha ]
    import_patches(repo, path, commit_list)

def usage(f, name):
    f.write("%s <commit>\n" % name)

def main(argv):
    usage = "usage: %prog [options] <commit sha>"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-P", "--patchset", dest="patchset", default=False, help="Import the whole patchset the specified commit belongs to", action="store_true")
    parser.add_option("-l", "--list-patchset", dest="do_list", default=False, help="Lists the commits in the same patchset as the specified commit", action="store_true")
    parser.add_option("-b", "--branch", dest="branch", default=DEFAULT_BRANCH, help="Use branch BRANCH in the specified repository", metavar="BRANCH")
    parser.add_option("-i", "--interval", dest="interval", default=DEFAULT_COMMIT_INTERVAL, help="Look for patchset patches within INTERVAL seconds", metavar="INTERVAL")
    (options, args) = parser.parse_args()

    patchset = options.patchset
    list_only = options.do_list
    do_import = options.patchset
    branch = options.branch
    interval = options.interval

    if len(args) < 1:
        parser.print_usage()
        return 1
    commit_sha = args[0]

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
        commit = repo.commit(commit_sha)
    except:
        sys.stderr.write("Unable to find commit %s in repository %s\n" % (commit, path))
        sys.exit(1)

    if not patchset and not list_only:
        import_single_patch(repo, path, commit_sha)
        return 0

    commit_list = list_patchset(repo, branch, interval, commit)

    if list_only:
        for c in commit_list:
            print(c)
        return 0

    if do_import:
        import_patches(repo, path, commit_list)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

