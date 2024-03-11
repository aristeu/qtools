#!/usr/bin/python3

import sys
import string
import hashlib
import re

_hunk_re = re.compile('^\@\@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? \@\@')
_filename_re = re.compile('^(---|\+\+\+) (\S+)')

def parse_patch(text):
    patchbuf = ''
    commentbuf = ''
    buf = ''

    # state specified the line we just saw, and what to expect next
    state = 0
    # 0: text
    # 1: suspected patch header (diff, ====, Index:)
    # 2: patch header line 1 (---)
    # 3: patch header line 2 (+++)
    # 4: patch hunk header line (@@ line)
    # 5: patch hunk content
    # 6: git diff rename extented header lines (similarity 100%)
    #
    # valid transitions:
    #  0 -> 1 (diff, ===, Index:)
    #  0 -> 2 (---)
    #  1 -> 2 (---)
    #  1 -> 6 (similarity index 100%)
    #  2 -> 3 (+++)
    #  3 -> 4 (@@ line)
    #  4 -> 5 (patch content)
    #  5 -> 1 (run out of lines from @@-specifed count)
    #  6 -> 0 (git rename headers processed, handle next diff if presented)
    #
    # Suspected patch header is stored into buf, and appended to
    # patchbuf if we find a following hunk. Otherwise, append to
    # comment after parsing.

    # line counts while parsing a patch hunk
    lc = (0, 0)
    hunk = 0
    patchline = []
    commentline = []

    for line in text.split('\n'):
        line += '\n'

        if state == 0:
            if line.startswith('diff ') or line.startswith('===') \
                    or line.startswith('Index: '):
                state = 1
                buf += line

            elif line.startswith('--- '):
                state = 2
                buf += line

            else:
                commentline.append(line)

        elif state == 1:
            buf += line
            if line.startswith('--- '):
                state = 2
            # This is for pure rename(similarity 100%).
            # Similarity less than 100% has hunk following the rename headers
            # and can be handled in state 1.
            elif line.startswith('similarity index 100%'):
                state = 6
            elif line.startswith('diff ') or line.startswith('Index: ') \
                     or line.startswith('deleted file ') \
                     or line.startswith('new file ') or line.startswith('====') \
                     or line.startswith('RCS file: ') or line.startswith('retrieving revision ') \
                     or line.startswith('similarity index ') or line.startswith('rename from ') \
                     or line.startswith('rename to '):
                state = 1
            else:
                state = 0
                commentline.append(buf)
                buf= ''

        elif state == 2:
            if line.startswith('+++ '):
                state = 3
                buf += line

            elif hunk:
                state = 1
                buf += line

            else:
                state = 0
                commentline.append(buf + line)
                buf = ''

        elif state == 3:
            match = _hunk_re.match(line)
            if match:

                def fn(x):
                    if not x:
                        return 1
                    return int(x)

                lc = list(map(fn, match.groups()))

                state = 4
                patchline.append(buf + line)
                buf = ''

            elif line.startswith('--- '):
                patchline.append(buf + line)
                buf = ''
                state = 2

            elif hunk:
                state = 1
                buf += line

            else:
                state = 0
                commentline.append(buf + line)
                buf = ''

        elif state == 4 or state == 5:
            if line.startswith('-'):
                lc[0] -= 1
            elif line.startswith('+'):
                lc[1] -= 1
            elif line.startswith('\ No newline at end of file'):
                # Special case: Not included as part of the hunk's line count
                pass
            elif line.startswith(' ') or line.startswith('\n') or line.startswith('\t'):
                # only consider part of the chunk count if it starts with a
                # valid character. this is done to catch line wraps in patch
                # submissions
                lc[0] -= 1
                lc[1] -= 1

            patchline.append(line)

            if lc[0] <= 0 and lc[1] <= 0:
                state = 3
                hunk += 1
            else:
                state = 5

        elif state == 6:
            buf += line
            if line.startswith('rename from '):
                state = 6
            elif line.startswith('rename to '):
                patchline.append(buf)
                buf = ''
                state = 0
            else:
                commentline.append(buf)
                buf = ''
                state = 0

        else:
            raise Exception("Unknown state %d! (line '%s')" % (state, line))

    commentline.append(buf)

    patchbuf = "".join(patchline)
    commentbuf = "".join(commentline)

    if patchbuf == '':
        patchbuf = None

    if commentbuf == '':
        commentbuf = None

    return (patchbuf, commentbuf)

def hash_patch(str):
    # normalise spaces
    if str is None:
        str = ''
    else:
        str = str.replace('\r', '')
        str = str.strip() + '\n'

    prefixes = ['-', '+', ' ']
    hash = hashlib.sha512()

    for line in str.split('\n'):

        if len(line) <= 0:
            continue

        hunk_match = _hunk_re.match(line)
        filename_match = _filename_re.match(line)

        if filename_match:
            # normalise -p1 top-directories
            if filename_match.group(1) == '---':
                filename = 'a/'
            else:
                filename = 'b/'
            filename += '/'.join(filename_match.group(2).split('/')[1:])

            line = filename_match.group(1) + ' ' + filename

        elif hunk_match:
            # remove line numbers, but leave line counts
            def fn(x):
                if not x:
                    return 1
                return int(x)
            line_nos = list(map(fn, hunk_match.groups()))
            line = '@@ -%d +%d @@' % tuple(line_nos)

        elif line[0] in prefixes:
            # if we have a +, - or context line, leave as-is
            pass

        else:
            # other lines are ignored
            continue

#        hash.update(line.encode('utf-8') + '\n')
        hash.update((line + '\n').encode('utf-8'))

    return hash.hexdigest()

def read_patch(f):
    patch = ''
    try:
        f = open(f)
        patch = f.read()
        f.close()
        (p, c) = parse_patch(patch)
        return p
    except:
        sys.stderr.write("Unable to open patch %s\n" % f)

def main(argv):
    if len(argv) < 3:
        sys.stderr.write("%s <patch 1> <patch 2>\n" % argv[0])
        return 1

    patch1 = read_patch(argv[1])
    patch2 = read_patch(argv[2])
    if hash_patch(patch1) != hash_patch(patch2):
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
