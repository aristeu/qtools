#!/bin/env python3
import sys
import os
import configparser
import git
import optparse
import datetime
import difflib
import errno
import re
import warnings
warnings.filterwarnings("ignore")

CONFIG_DEFAULT = '~/.config/qtools/config'
# we can add an option to specify branch and another to do it automatically (git branch -a --contains <sha>)
DEFAULT_BRANCH = 'master'

def update_cache(repo, cache, branch, last):
    try:
        os.mkdir(cache)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise(error)

    for c in ['a','b','c','d','e','f', '0','1','2','3','4','5','6','7','8','9']:
        try:
            os.mkdir("%s/%s" % (cache, c))
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise(error)

    regex = re.compile('.*Fixes:\ ([0-9a-f]+)\ .*', re.S)
    ret = None
    for c in repo.iter_commits(branch):
        if ret is None:
            ret = c.hexsha
        if c.hexsha == last:
            break

        msg = c.message
        if type(msg) is bytes:
            try:
                msg = msg.decode('utf-8', errors='ignore')
            except Exception as error:
                msg = None
                pass
            if msg is None:
                msg = msg.decode('iso8859-1', errors='ignore')

        match = re.match(regex, msg)
        if not match:
            continue

        try:
            commit = repo.commit(match.group(1))
        except:
            sys.stderr.write("Warning: commit %s fixes %s but %s can't be found\n" % (c.hexsha, match.group(1), match.group(1)))
            pass
            continue

        commit_sha = commit.hexsha
        filename = "%s/%s/%s" % (cache, commit_sha[0], commit_sha)
        try:
            f = open(filename, "r")
            lines = f.readlines()
            f.close()
            if c.hexsha + "\n" in lines:
                continue
        except:
            pass

        f = open(filename, "a+")
        f.write("%s\n" % c.hexsha)
        f.close()
    return ret

def get_fixes_from_cache(cache, commit_sha):
    output = []
    try:
        f = open("%s/%s/%s" %(cache, commit_sha[0], commit_sha), "r")
        for c in f.readlines():
            output.append(c.replace('\n', ''))
    except:
        pass
    return output

# here we recursively look for patches that fix the given one
def get_fixes_single(cache, commit_sha, verbose):
    current_list = [commit_sha]
    final_list = []

    while len(current_list) > 0:
        for c in current_list:
            fixes = get_fixes_from_cache(cache, c)
            for i in fixes:
                if i not in current_list:
                    current_list.append(i)
                if i not in final_list:
                    if verbose:
                        sys.stderr.write("%s is fixed by %s\n" % (c, i))
                    final_list.append(i)
            current_list.remove(c)

    return final_list

def get_fixes(cache, verbose):
    output = []

    try:
        f = open("patches/series", "r")
        series = [s.replace(".patch\n", "") for s in f.readlines()]
    except Exception as error:
        raise("Unable to open patch/series (%s)" % str(error))

    for c in series:
        fixes = get_fixes_single(cache, c, verbose)
        for i in fixes:
            if i not in output and i not in series:
                output.append(i)

    return output

def check_update_state(repo, last):
    if last is None:
        sys.stderr.write("Cache is not initialized, run with -u then try again\n")
    try:
        commit = repo.commit('HEAD')
        if commit.hexsha != last:
            sys.stderr.write("Warning: cache is not up-to-date: last scanned commit: %s, HEAD is %s\n" % (last, commit.hexsha))
    except Exception as error:
        sys.stderr.write("Unable to get 'HEAD' commit in the specified tree (%s)\n" % str(error))

def main(argv):
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-u", "--update", dest="do_update", default=False, help="Update cache using configured git repository", action="store_true")
    parser.add_option("-s", "--single", dest="do_single", help="Only list fixes for a given COMMIT and ignores all patches already in series", metavar="COMMIT")
    parser.add_option("-v", "--verbose", dest="do_verbose", default=False, help="Show the reason why each commit is picked as fix", action="store_true")
    (options, args) = parser.parse_args()

    do_update = options.do_update
    do_verbose = options.do_verbose

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
        if 'fixes' not in config:
            sys.stderr.write("Fixes section not found in the config file\n")
            return 1
        if 'cache' not in config['fixes']:
            sys.stderr.write("Fixes section in the config file doesn't contain cache=\n")
            return 1
        cache = config['fixes']['cache']
        last = None
        if 'last' in config['fixes']:
            last = config['fixes']['last']
    except Exception as ex:
        sys.stderr.write("Unable to read the config file, which is mandatory for now\n")
        raise(ex)
        return 1

    repo = git.Repo(path)
    try:
        repo = git.Repo(path)
    except:
        sys.stderr.write("Unable to open git repo at %s\n" % path)
        return 1

    if do_update:
        # for now, all we care is Linus' master branch
        config['fixes']['last'] = update_cache(repo, cache, "master", last)
        f = open(os.path.expanduser(CONFIG_DEFAULT), "w")
        config.write(f)
        f.close()
        return 0

    check_update_state(repo, last)

    if options.do_single:
        fixes = get_fixes_single(cache, options.do_single, do_verbose)
        if not do_verbose:
            for c in fixes:
                print(c)
        return 0

    fixes = get_fixes(cache, do_verbose)
    if not do_verbose:
        for c in fixes:
            print(c)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))

