#!/usr/bin/env bash
version_file="pywrstat/version.py"
cat "${version_file}"
if ! git diff --name-only ${1:-master} | grep "${version_file}" >/dev/null
then
  echo "!! Please bump __version__ in ${version_file}"
  exit 1
fi
echo "New version is valid"
exit 0
