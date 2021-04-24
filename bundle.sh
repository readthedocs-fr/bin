#!/bin/bash 
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"/bin

test -e .git && echo This script remove assets, better not run it in development. && exit 1

for dir in assets/scripts assets/styles
do
    cd $dir
    for oldfile in $(ls)
    do
        sum=$(sha1sum $oldfile | cut -d ' ' -f1)
        stem="${oldfile%.*}"
        ext="${oldfile##*.}"
        newfile="$stem-$sum.$ext"
        python3 -m "r${ext}min" < "$oldfile" > "$newfile"
        gzip "$newfile"
        sed -ri "/<(script|link).*(href|src)/s/$oldfile/$newfile/" ../views/*.html
        rm "$oldfile"
    done
    cd ../..
done
