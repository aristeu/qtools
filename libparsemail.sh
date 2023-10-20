#!/bin/bash
# This file is part of trk-tools.
#
# Copyright 2008 Red Hat Inc
#
# trk-tools is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# trk-tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with trk-tools; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


# returns the email author
# $1: input file
function get_from
{
	grep ^From: "$1" | head -n 1 | cut -f 2- -d ' ';
}

# returns the email subject
# $1: input file
function get_subject
{
	cat "$1" | formail -x Subject | cut -f 2- -d ' ' | sed -e ":begin; s/\n/\ /; N; b begin;";
}

# returns the mail id
# $1: input file
function get_mail_id
{
	grep -i ^Message-Id: "$1" | head -n 1 | sed -e "s/.*<\([^>]*\)\>.*/\1/";
}

# returns the in reply to field (answer to which mail id)
# $1: input file
function get_in_reply_to
{
	grep -i ^In-Reply-To: "$1" | head -n 1 | sed -e "s/.*<\([^>]*\)\>.*/\1/";
}

# returns a list of reference mail-ids
# $1: input file
function get_references
{
	cat "$1" |
		sed -e "{ :newline; s/References: //; t next; D; N; b newline; :next; h; N; s/\t//; T end; H; b next; :end; g }";
}

# checks if the email has an ACK
# $1: input file
# returns: 1 in case it has a clear ACK, 0 if it doesn't, 2 if "ACK" was found
#	   on the text
function has_ack
{
	if [ -n "$(egrep -i -e "^[aA][cC][cK][\.]?|^Acked-by" "$1")" ]; then
		return 1;
	elif [ -n "$(egrep -i -e "[\^\ \t]+ACK|Acked-by" "$1")" ]; then
		return 2;
	fi
	return 0;
}

# checks if the email has a NAK
# $1: input file
# returns: 1 in case it has a clear NAK, 0 if it doesn't, 2 if "NAK" was found
#	   on the text
function has_nak
{
	if [ -n "$(egrep -i -e "^NAK$" "$1")" ]; then
		return 1;
	elif [ -n "$(egrep -i -e "[^\ \t]\+NAK" "$1")" ]; then
		return 2;
	fi
	return 0;
}

# returns a list separated by spaces of the BZ#s referenced on the email
# $1: input file
function get_bz_references
{
	# If the BZ# is anywhere but the subject or body, the sender is fail.
	# 100644 is a common number in git diffs and no bug # can start w/a 0, so filter those out.
	cat "$1" | formail -k -X From: -X Subject: |
		egrep -i -e "Bugzilla|BZ|show_bug.cgi|bugzilla.redhat.com/|[\t\ ^][0-9]\{6-7\}[\t\ ^.]*" |
		sed -n -e "s/.*[Bb][Zz][#]\?[\ -]*\([0-9]\+\).*/\1/gp;s/.*show_bug.cgi?id=\([0-9]\+\).*/\1/gp;s/[^0-9]\+\([0-9]\{6,7\}\)[^0-9]*/\1/gp;s,http://bugzilla.redhat.com/\([0-9]\+\).*,\1,gp" |
		grep -v "100644" | grep -v "^0" |
		sort -u;
}

# returns a list of the CVEs referenced on the email
# $1: input file
function get_cve_references
{
	grep CVE "$1" |
		grep -v X-Patchwork-Tag |
		sed -e "s/.*\(CVE-[0-9]\{4\}-[0-9]\{4\}\).*/\1/g" |
		sort -u;
}

# returns what is believed to be the "main" BZ
# $1: input file
function get_main_bz
{
	get_bz_references "$1" |
		head -n 1;
}

# returns a list of possible git commits in the email
# $1: input file
function get_git_references
{
	# Will accept #, ?, <space>, = as characters before
	cat $1 | sed -n -e "s/.*[#?\ =]\([a-f0-9]\{40\}\).*/\1/p" |
		sort -u;
}

# returns the first commit id that is found using the strict "^commit <sha>\n"
# format
function get_git_commit
{
	egrep -e "^commit|^\(cherry picked from commit" $1 | head -n 1 | sed -e "s/.*\([a-f0-9]\{40\}\).*\$/\1/"
}

# returns the email date
# $1: input file
function get_date
{
	date -d "$(grep "^Date: " "$1" | cut -f 2- -d ':')";
}

# parses the email file and writes out the header and body in different files
# $1: input file
# $2: header file
# $3: body file
function split_mail
{
#	if [ -z "$(cat $1 | head -n 1 | grep "^From\ ")" ]; then
#		# no headers
#		cat "$1" >"$3";
#		echo >"$2";
#		return;
#	fi
	cat "$1" | sed -n "1,/^\$/p; /^\$/, \$w $3" >"$2";
}

# parses the email file and writes out the body and email in different files
# $1: input file
# $2: body file
# $3: patch file
function split_patch_from_body
{
	# check if the file has Index: lines
	if [ -n "$(grep "^[Ii]ndex: " "$1")" ]; then
		cat "$1" | sed -n "0,/^[Ii]ndex:\ /p; /^[Ii]ndex:\ /, \$w $3" |
			   sed -e "s/^[Ii]ndex:\ .*//" >"$2";
	# check if it has "diff -" lines
	elif [ -n "$(grep "^diff -" "$1")" ]; then
		cat "$1" | sed -n "0,/^diff\ -/p; /^diff\ -/, \$w $3" |
			   sed -e "s/^diff\ -.*//" >"$2";
	# or git's index ...
	elif [ -n "$(grep "^index [0-9a-f].*\ [0-9]" "$1")" ]; then
		cat "$1" | sed -n "0,/^index\ [0-9a-f].*\ [0-9]/p; /^index\ [0-9a-f].*\ [0-9]/, \$w $3" |
			   sed -e "s/^index\ [0-9a-f].*\ [0-9].*//" >"$2";
	# otherwise, just look for ^---
	else
		cat "$1" | sed -n "1,/^---\ /p; /^---\ /, \$w $3" >"$2";
	fi
}

# checks if a given file contains a patch
# $1: input file
# return 1 if the file contains a patch, 0 otherwise
function has_patch
{
	# FIXME: we could do better, not sure if it's needed
	if [ -n "$(grep "^+++\ " "$1")" ]; then
		return 1;
	fi
	return 0;
}

# checks if a given mail body has attachments
# $1: body file
# returns 0 if it does, 1 if it doesn't
function mailparse_has_attachments
{
	if [ -n "$(grep -i "Content-Type: multipart" "$1")" ]; then
		return 0;
	fi
	return 1;
}

# unpack all attachments out of a mail body and print in plain text on
# stdout
# $1: body file
# returns 0 in case of success, 1 in case of error
function mailparse_munpack
{
	local tmp i list ifs;

	tmp="$(mktemp -d)";
	list=$(munpack -q -C "$tmp" -t "$1" 2>/dev/null | sed -e "s/\ (.*)\$//");
	ifs=$IFS;
	IFS='
';
	for i in $list; do
		cat "$tmp/$i";
	done
	IFS=$ifs;
	rm -Rf "$tmp";
	return 0;
}

# extract the RHEL version out of the subject
# $1 input file
function get_rhel_version
{
	get_subject "$1" |
		sed -n "s/.*[rR][hH][eE][lL][-\ ]\?\([0-9]\)[\.]\?\([0-9]*\).*/\1.\2/; T; p;" |
			sed -e "s/\.$/.x/";
}

# function to get a patch name based on subject
# $1: subject
function subj_to_name
{
	local subj="$1";
	local pre="";
	local num=2;

	#make sure the first word has a : or surrounded by []
	#else add a stub misc- to it
	pre="$(echo "$subj" | awk '{print $1}' | egrep ":$|^\[.*\]$")"
	test -n "$pre" || subj="misc ${subj}"

	#convert all non alpha/numerics into -'s
	#this forms the patch name for the rpm spec file
	name="$(echo "$subj" |
		sed -e "{ s/[^a-zA-Z0-9_-]/-/g;
			  s/--*/-/g;
			  s/^[.-]*//g;
			  s/[.-]*$//g }")"
	test -z "$SPECFILE" && name="$(echo "$name" | tr A-Z a-z)"

	case "$pre" in
	*git*|*patch*|*stable*|*tag*) patchname="${name}" ;;
	*) patchname="linux-2.6-${name}" ;;
	esac

	while test -f "$SOURCES/${patchname}.patch"; do
		patchname="linux-2.6-${name}-${num}"
		let num=$num+1
	done
	echo "${patchname}.patch"
}

