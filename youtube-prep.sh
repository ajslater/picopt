#!/bin/sh
ffmpeg -i $1 -vcodec mpeg4 -sameq -b 11000k -acodec mp3 -ac 1 $1.youtube.avi
