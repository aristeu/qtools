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
DEFAULT_BRANCH = 'master'
DEFAULT_CACHE_DIR= '~/.qtools/backport'
TEMP_REMOTE = "qtools_upstream"

def create_backport_cache(path):
    for c in string.digits + string.ascii_lowercase[:6]:
        try:
            os.mkdir("%s/%s" % (path, c))
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise(error)

def create_temp_remote(repo, upstream):
    remove_temp_remote(repo)
    remote = repo.create_remote(TEMP_REMOTE, upstream)
    remote.fetch()

def remove_temp_remote(repo):
    try:
        repo.delete_remote(TEMP_REMOTE)
    except:
        pass

def update_backport_cache(repo, cache, branch, upstream):
    try:
        os.mkdir(cache)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise(error)

    create_temp_remote(repo, upstream)

    # FIXME - make upstream's branch configurable
    merge_base = repo.merge_base(branch, "%s/%s" % (TEMP_REMOTE, 'master'))[0]

    for c in repo.iter_commits(branch):
        if c == merge_base:
            break

        if len(c.parents) > 1:
            #sys.stderr.write("Ignoring merge %s\n" % c.hexsha)
            continue

        msg = c.message
        if type(msg) is bytes:
            try:
                msg = msg.decode('utf-8', errors='ignore')
            except Exception as error:
                msg = None
                pass
            if msg is None:
                msg = msg.decode('iso8859-1', errors='ignore')

        while True:
            match = re.findall('^[\ ]*commit\ ([0-9a-f]+)$', msg, re.MULTILINE)
            if match:
                break
            match = re.findall('^[\ ]*\(cherry\ picked\ from\ commit\ ([0-9a-f]+)\)$', msg, re.MULTILINE)
            if match:
                break
            match = re.findall('^[\ ]*[uU]pstream\ [sS]tatus:\ [rR][hH][eE][lL].*', msg, re.MULTILINE)
            if match:
                match = None
                break
            match = re.findall('\[redhat\]\ kernel-.*', msg, re.MULTILINE)
            if not match:
                #sys.stderr.write("Unable to find upstream commit in commit %s\n" % c.hexsha)
            match = None
            break

        if match is None:
            continue

        upstream = match[0]
        backport = c.hexsha

        directory = os.path.expanduser("%s/%s" % (cache, upstream[0]))
        os.makedirs(directory, exist_ok = True)

        filename = "%s/%s" % (directory, upstream)
        f = open(filename, "w")
        f.write("%s" % backport)
        f.close()

    remove_temp_remote(repo)

def get_default_repo(config):
    repo = ''
    if 'repository' not in config:
        raise Exception("Repository section not found in the config file")
    if 'default' not in config['repository']:
        raise Exception("No 'default' in repository section")
    default_repo = "repo-%s" % config['repository']['default'];
    if default_repo not in config:
        raise Exception("No default repository %s section exists" % default_repo)
    return default_repo

def get_repo_path(config, repo):
        if 'path' not in config[repo]:
            raise Exception("Repository section in the config file doesn't contain path=")
        return config[repo]['path']

def get_repo_branch(config, repo):
        if 'branch' not in config[repo]:
            sys.stdout.write("Repository section in the config file doesn't contain branch, using 'master'\n")
            return 'master';
        return config[repo]['branch']

def get_backport_cache(config, filename, repo):
        if 'cache' not in config[repo]:
            # FIXME - make default_cache_dir configurable
            directory = os.path.expanduser("%s/%s" % (DEFAULT_CACHE_DIR, repo))
            try:
                os.makedirs(name = directory, exist_ok = True)
            except OSError as error:
                if error.errno != errno.EEXIST:
                    raise(error)

            f = open(os.path.expanduser(filename), "w")
            config[repo]['cache'] = directory
            config.write(f)
            f.close()

            return directory
        return os.path.expanduser(config[repo]['cache'])

def get_upstream(config, repo):
        if 'upstream' not in config['repository']:
            raise Exception("Repository section doesn't have upstream=")
        name = config['repository']['upstream']
        return config['repo-%s' % name]['path']

def main(argv):
    config = configparser.ConfigParser()
    config.read(os.path.expanduser(CONFIG_DEFAULT))
    default_repo = get_default_repo(config)

#    parser.add_option("-u", "--update", dest="do_update", default=False, help="Update cache using configured git repository", action="store_true")
#    parser.add_option("-s", "--single", dest="do_single", help="Only list fixes for a given COMMIT and ignores all patches already in series", metavar="COMMIT")
#    parser.add_option("-v", "--verbose", dest="do_verbose", default=False, help="Show the reason why each commit is picked as fix", action="store_true")
#    (options, args) = parser.parse_args()
#
#    do_update = options.do_update
#    do_verbose = options.do_verbose

#    usage = "usage: %prog [options]"
#    parser = optparse.OptionParser(usage=usage)
#    parser.add_option("-u", "--update", dest="do_update", default=False, help="Update cache using configured git repository", action="store_true")
#    do_update = options.do_update

    # for now
    repo = default_repo

    branch = get_repo_branch(config, repo)
    upstream = get_upstream(config, repo)
    path = get_repo_path(config, repo)
    cache = get_backport_cache(config, CONFIG_DEFAULT, repo)

    try:
        repo = git.Repo(path)
    except:
        sys.stderr.write("Unable to open git repo at %s\n" % path)
        return 1

    update_backport_cache(repo, cache, branch, upstream)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

