#!/bin/bash
IFS=$'\n'
for i in $*; do 
  filtered=`echo "$i" | sed 's/\[/(/' | sed 's/\]/)/'`
  if [ "$filtered" != $i ]; then
      echo mv "$i" "$filtered"
      mv "$i" "$filtered"
  fi
done;
