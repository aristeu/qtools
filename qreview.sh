#!/bin/bash

red='\033[0;31m';
green='\033[0;32m';
nc='\033[0m';

if [ ! -d 'patches' ]; then
	echo "No patches/ found";
	exit 1;
fi

function line
{
	for i in $(seq 2 80); do
		echo -n "*";
	done;
	echo;
}

while [ 1 ]; do
	applied=$(quilt applied 2>/dev/null| wc -l);
	total=$(quilt series | wc -l);

	if [ $applied -gt 0 ]; then
		quilt header | sed -e "s/^/\t/";
		quilt top;
		quilt diff | diffstat -p 1 -l;
	elif [ -f patches/mr ]; then
		lab mr show $(<patches/mr);
	else
		echo "No patches applied";
	fi
	line;
	if [ $applied -gt 0 ]; then
		m=$(umatch);
		if [ $m = "true" ]; then
			match="${green}yes${nc}";
		else
			match="${red}no${nc}";
		fi
		printf "${green}${applied}${nc}/${red}${total}${nc} Match upstream: ${match}\n"
	else
		printf "${green}${applied}${nc}/${red}${total}${nc}\n"
	fi
	extra="";
	if [ -n "$(quilt header | grep Y-Commit)" ]; then
		extra="[Z]stream comparison ";
	fi
	line;
	echo "[h]eader [q]compare [u]compare [p]ush p[o]p [f]orce apply [m]r show [U]pstream file compare ${extra}[e]xit"
	read -d'' -s -n1 answer;
	case $answer in
	'h')
		quilt header -e;
	;;
	'q')
		qcompare;
	;;
	'u')
		ucompare;
	;;
	'p')
		quilt push;
	;;
	'o')
		quilt pop;
	;;
	'f')
		quilt push -f;
		exit 0;
	;;
	'm')
		lab mr show $(<patches/mr);
	;;
	'e')
		exit 0;
	;;
	'U')
		for i in $(quilt files); do
			ufcompare $i;
		done
	;;
	'Z')
		if [ -n "$extra" ]; then
			zcompare;
		fi
	;;
	*)
		true;
	;;
	esac
done
