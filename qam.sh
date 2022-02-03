#!/bin/bash

username="$(git config --get user.name)";
email="$(git config --get user.email)";
user="$(echo $email | sed -e "s/@.*//")";

if [  -z "$username" -o -z "$email" ]; then
	echo "Configure name and email in git" >&2;
	exit 1;
fi

for i in $(quilt series); do
	file="patches/$(basename $i)";
	msgid="$(basename $i .patch)@redhat.com";
	subject="$(head -n 1 $file)";

	echo "From ${user} $(date "+%a %b %d %H:%M:%S %Y")";
	echo "Date: $(date "+%a, %d %b %Y %H:%M:%S %z")";
	echo "Status: RO";
	echo "Content-Type: text/plain; charset=\"utf-8\"";
	echo "From: ${username} <${email}>";
	echo "Message-id: <${msgid}>";
	echo "To: ${email}";
	echo "Subject: ${subject}";
	echo;
	tail -n +3 ${file};
	echo;
done
