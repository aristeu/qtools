#!/bin/env python3
import sys
import os
import configparser
import git
import subprocess
import optparse
import re

CONFIG_DEFAULT = '~/.config/qtools/config'
# We only look at patches committed within 10min of the target one
DEFAULT_COMMIT_INTERVAL=600
# we can add an option to specify branch and another to do it automatically (git branch -a --contains <sha>)
DEFAULT_BRANCH = 'master'

def write_single_patch(path, series, commit):
    patch = "%s.patch" % commit
    f = open("patches/%s" % patch, "w")
    # ugh. Couldn't make commit.diff work the same way
    formatted_patch = subprocess.check_output(["git", "-C", path, "log", "-p", "-1", commit.hexsha])
    # ffs
    try:
        f.write(formatted_patch.decode('utf-8'))
    except:
        f.write(formatted_patch.decode('iso8859-1'))
    f.close()
    series.write("%s\n" % patch)

# gets a list of patches in the same patchset by considering date and author
def list_patchset(repo, branch, interval, commit):
    author_email = commit.author.email
    date = commit.committed_date

    commit_list = []
    commit_sha_list = []
    found_commit = False
    for c in repo.iter_commits(branch):
        if c.committed_date < (date - interval):
            # we're done looking
            break
        if c.committed_date < (date + interval):
            if c.hexsha == commit.hexsha:
                found_commit = True
            if c.author.email == author_email:
                commit_sha_list.append(c.hexsha)
                commit_list.append(c)
            else:
                if found_commit:
                    # we did it,
                    break
                # author might have changed and we didn't find the target commit
                commit_list.clear()
                commit_sha_list.clear()

    if len(commit_list) == 0:
        sys.stderr.write("Commit %s not found in branch %s. Specify a different repo or branch\n" % (commit, branch))
        sys.stderr.write("Until an option is implemented to do this automatically, run 'git branch -a --contains %s'\n" % commit)
        return []

    commit_sha_list.reverse()
    return (commit_list, commit_sha_list)

def import_patches(repo, path, commit_list):
    try:
        os.mkdir("patches")
    except FileExistsError:
        pass
    except OSError as error:
        sys.stderr.write("Unable to create directory patches: %s\n" % str(error))
        sys.exit(1)

    mode = "r+"
    if not os.path.exists("patches/series"):
        mode = "w+"

    try:
        series = open("patches/series", mode)
    except Exception as ex:
        raise("Unable to open series file: %s\n" % str(ex))

    lines = series.readlines()
    for commit in commit_list:
        patch = "%s.patch" % commit.hexsha
        if ("%s\n" % patch) in lines:
            print("Skipping %s: already in series" % patch)
            continue
        write_single_patch(path, series, commit)
    series.close()

def get_commit_from_file(repo, sha):
    # first try by filename
    try:
        commit = repo.commit(sha)
    except:
        commit = None
        pass

    if commit:
        return commit

    # then by content
    r = re.compile("^commit ([0-9a-f]*)")
    try:
        f = open("patches/%s.patch" % sha, "r")
    except:
        sys.stderr.write("Unable to find patch file %s.patch\n" % sha)
        pass
        return
    for l in f.readlines():
        match = r.match(l)
        if match:
            found_sha = match.group(1)
            try:
                commit = repo.commit(found_sha)
                return commit
            except Exception as ex:
                sys.stderr.write("Unable to find commit %s in repository\n" % found_sha)
                pass
                continue
    return None

def check_series(repo, branch, interval):
    try:
        series = open("patches/series", "r")
    except Exception as ex:
        sys.stderr.write("Unable to open series file: %s\n" % str(ex))
        return 1

    lines = series.read().splitlines()
    commit_sha_list = []
    for l in lines:
        if l[0] == '#':
            continue
        commit_sha_list.append(l.replace('.patch', ''))

    missing_list = []
    for c in commit_sha_list:
        commit = get_commit_from_file(repo, c)
        if commit is None:
            continue

        (clist, sha_list) = list_patchset(repo, branch, interval, commit)
        if len(sha_list) == 0:
            return 1

        for p in sha_list:
            if p not in commit_sha_list:
                if p not in missing_list:
                    missing_list.append(p)

    if len(missing_list) > 0:
        for p in missing_list:
            print("%s" % p)

    return 0

def usage(f, name):
    f.write("%s <commit>\n" % name)

def main(argv):
    usage = "usage: %prog [options] <commit sha | ->"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-g", "--git", dest="git", default=None, help="Specify an alternate git repository path instead of the configuration one", metavar="GIT")
    parser.add_option("-P", "--patchset", dest="patchset", default=False, help="Import the whole patchset the specified commit belongs to", action="store_true")
    parser.add_option("-l", "--list-patchset", dest="do_list", default=False, help="Lists the commits in the same patchset as the specified commit", action="store_true")
    parser.add_option("-b", "--branch", dest="branch", default=DEFAULT_BRANCH, help="Use branch BRANCH in the specified repository", metavar="BRANCH")
    parser.add_option("-i", "--interval", dest="interval", default=DEFAULT_COMMIT_INTERVAL, help="Look for patchset patches within INTERVAL seconds", metavar="INTERVAL")
    parser.add_option("-c", "--check", dest="check", default=False, help="Checks if current quilt series has missing patches from the patchset(s) in it", action="store_true")
    (options, args) = parser.parse_args()

    path = options.git
    patchset = options.patchset
    list_only = options.do_list
    do_import = options.patchset
    branch = options.branch
    interval = options.interval
    check = options.check

    if len(args) < 1 and check is False:
        parser.print_usage()
        return 1

    if path is None:
        config = configparser.ConfigParser()
        try:
            config.read(os.path.expanduser(CONFIG_DEFAULT))
            if 'repository' not in config:
                sys.stderr.write("Repository section not found in the config file\n")
                return 1
            if 'upstream' not in config['repository']:
                sys.stderr.write("No 'upstream' in repository section\n")
                return 1
            default_repo = "repo-%s" % config['repository']['upstream'];
            if default_repo not in config:
                sys.stderr.write("No default repository %s section exists\n" % default_repo)
                return 1
            if 'path' not in config[default_repo]:
                sys.stderr.write("Repository section in the config file doesn't contain path=\n")
                return 1
            path = config[default_repo]['path']
        except:
            sys.stderr.write("Unable to read the config file, which is mandatory for now\n")
            return 1

    repo = git.Repo(path)
    try:
        repo = git.Repo(path)
    except:
        sys.stderr.write("Unable to open git repo at %s\n" % path)
        return 1

    if check:
        return check_series(repo, branch, interval)

    commit_sha_list = []
    commit_list = []

    # handle standard input
    if args[0] == '-':
        for item in sys.stdin.read().split('\n'):
            if len(item.replace(' ', '')) == 0:
                continue
            commit_sha_list.append(item)

    else:
        commit_sha_list = args[0].split(',')

    # we have the user provided list, now gather commits objects
    for commit_sha in commit_sha_list:
        try:
            commit = repo.commit(commit_sha)
            commit_list.append(commit)
        except Exception as ex:
            sys.stderr.write("Unable to find commit %s in repository %s\n" % (commit_sha, path))
            # TODO: add a force option to ignore
            sys.exit(1)

    # now, if asked, add patches in the same patchset
    output_sha_list = []
    output_list = []
    if patchset or list_only:
        for commit in commit_list:
            (clist, sha_list) = list_patchset(repo, branch, interval, commit)
            for sha in sha_list:
                if sha not in output_sha_list:
                    output_sha_list.append(sha)
            for c in clist:
                if c not in output_list:
                    output_list.append(c)

        # list_patchset will expand the commit id automatically, no need to redo it
        commit_sha_list = output_sha_list
        for sha in output_list:
            if sha not in commit_list:
                commit_list.append(sha)

    if len(commit_list) == 0:
        sys.exit(1);

    # only listing
    if list_only:
        for c in commit_sha_list:
            print(c)
        return 0

    # applying
    import_patches(repo, path, commit_list)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

