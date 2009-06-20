#!/bin/bash
for i in $*; do
    cd $i
    find . -name "*\[*" -print0 | xargs -0 kill-square-brackets.sh
done;
