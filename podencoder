#!/bin/bash

# podencoder - the flexible video encoder for iPods and other devices
# Copyright (C) 2006-7, Mark Pilgrim
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA

version="0.20070117.0"

# Revision history:
# 0.20070117.0 - try to detect ARcoOS/RipGuard bad sectors
# 0.20061206.0 - broke out encoding parameters and allowed app-specific overrides
# 0.20061125.0 - changed to mencoder + MP4Box (gpac.sf.net)
# 0.20060922.0 - updated to match latest ffmpeg svn (changed option names)
# 0.20060901.0 - autodetect whether we are in a tty or graphical environment
#              - removed useless use of wc -l
#              - reflowed lines to 79 characters
# 0.20060831.0 - removed bashisms, changed to /bin/sh
# 0.20060830.0 - initial release

# set up some reasonable defaults
appname=`basename "$0"`
appdescription="Encode video for iPod 5G"
confname=."$appname"rc
device=/dev/dvd
outputdir=.
scratchdir=/tmp
tracks=
chapters=
naming="%d-%t"
index=1
videobitrate=450
audiobitrate=128
crop=
fitto4x3=
scale=320:-10
x264encopts_required="vbv_maxrate=768:vbv_bufsize=244:nocabac:level_idc=13"
x264encopts_optional="turbo=1:me=umh:frameref=5:subq=6:partitions=all:trellis=1:direct_pred=auto:threads=auto"
x264encopts=

# import conf file, possibly overriding defaults
[ -r ~/"$confname" ] && . ~/"$confname"

# parse command-line arguments, possibly overriding configuration file
while getopts ":a:b:c:fi:n:o:s:t:vx:" options; do
  case $options in
    a) audiobitrate=$OPTARG;;
    b) videobitrate=$OPTARG;;
    c) crop=$OPTARG;;
    f) fitto4x3=1;;
    i) index=$OPTARG;;
    n) naming=$OPTARG;;
    o) outputdir=$OPTARG;;
    s) scratchdir=$OPTARG;;
    t) tracks=$OPTARG;;
    x) x264encopts=$OPTARG;;
    v) cat <<EOF
$appname $version
Copyright (C) 2006, Mark Pilgrim
$appname is free software.  You can redistribute it and/or modify it under
the terms the GNU General Public License version 2 or, at your option,
any later version published by the Free Software Foundation.  There is
NO WARRANTY, to the extent permitted by law.
EOF
       exit 1;;
    *) cat <<EOF
Usage: $appname [OPTIONS] [SOURCE]
$appdescription

SOURCE can be DVD device, directory containing VIDEO_TS, or video file in
any format.  If no SOURCE, reads from default device (/dev/dvd).

All flags are optional
  -o    output directory (default=.)
  -s    scratch directory for temp files (default=/tmp)
  -t    track number as comma-separated list of track numbers, or "all"
  -n    naming scheme for output files, see below
  -i    start index for naming scheme (default=1)
  -b    video bitrate (default=450)
  -a    audio bitrate (default=128)
  -c    crop rectangle as w:h[:x:y] (default=autodetect)
  -f    fit to 4x3 aspect ratio when auto-cropping widescreen video
  -x    additional -x264encopts parameters as colon-separated list
  -h    display this help and exit
  -v    display version number and exit

Naming scheme (-n flag) determines output filename(s).  Do not include a
file extension; it is appended automatically.
  %d    disc title (from device or directory name)
  %t    physical track number
  %i    index number (starts at 1 or -i and increments for each track)

Examples:
  $appname             Prompt and encode tracks from default DVD device
  $appname -t 2        Encode track 2 from default DVD device
  $appname ./BBSDOC/   Prompt and encode tracks from ./BBSDOC/ directory
  $appname -t "2,3,4"  Encode tracks 2, 3, and 4 from default DVD device
  $appname -t "2,3,8" -i 4 -n "%d-%i" ./BBSDOC/
     Encode tracks 2, 3, and 8 from ./BBSDOC/ directory
     and name them BBSDOC-04.mp4, BBSDOC-05.mp4, and BBSDOC-06.mp4

Also reads configuration settings from ~/$confname
  device=        default DVD device
  outputdir=     output directory (like -o)
  scratchdir=    scratch directory (like -s)
  tracks=        track numbers (like -t)
  naming=        naming scheme (like -n)
  index=         start index (like -i)
  videobitrate=  video bitrate (like -b)
  audiobitrate=  audio bitrate (like -a)
  crop=          crop rectangle (like -c)
  fitto4x3=      fit widescreen video to 4x3 aspect ratio (like -f)
  scale=         scale rectangle
  x264encopts=   additional encoding parameters (like -p)
                 (can override some or all of x264encopts_required and
                  x264encopts_optional if you know what you're doing)

Report bugs to <mark@diveintomark.org>.
EOF
       exit 1;;
  esac
done
# remove flags so $1 points to input file or device
shift $(($OPTIND - 1))
# get input file or device, if specified (otherwise use the default device)
[ -n "$1" ] && device="$1"
# determine whether we should use GUI dialogs or console output
if tty -s; then :; else gui=1; fi

# GUI-aware error function
die () {
  if [ $gui ]; then
    zenity --error --title="$appname" --text="$1.  Encoding failed."
  else
    echo "$1.  Encoding failed." >/dev/stderr
  fi
  exit 1
}

warning () {
  if [ $gui ]; then
    zenity --warning --title="$appname" --text="$1."
  else
    echo "Warning: $1" >/dev/stderr
  fi
}

# clean up temp files on exit or break
CleanUpTempFiles () {
  if [ -f "$device" ]; then
    # if source is file, we don't make a temporary copy,
    # so don't delete the original!
    :
  else
    rm -f "$tempfile"
    rm -f "$inputfile"
    rm -f "$mplayerlogfile"
  fi
  rm -f "$mencoderlog"
  rm -f "$mencoderpasslogfile"
  if [ -n "$avioutput" ]; then
    rm -f "$avioutput".avi
    rm -f "$avioutput".h264
    rm -f "$avioutput".aac
  fi
}

# clean up processes and temp files on break
TrapBreak () {
  trap "" HUP INT TERM
  # if mplayer or mencoder or zenity are still running, kill them
  [ -n "$zenpid" ] && kill "$zenpid" 2>/dev/null
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
  CleanUpTempFiles
  exit 1
}

# GUI-aware progress function that parses mencoder's output
# and converts it to a simple percent-complete indicator
DisplayEncodingProgress () {
  if [ -z "$track" ]; then
    progresstext="Encoding $inputfile (pass $pass of 2)"
  else
    progresstext="Encoding track $track (pass $pass of 2)"
  fi
  if [ $gui ]; then
    (
      while ps | grep "$pid " >/dev/null
      do
        secondsCompleted=`tail -c 90 "$mencoderlog" | \
                          awk -F"time=" {'print $2'} | cut -d"." -f 1`
        [ -n "$secondsCompleted" ] || secondsCompleted=0
        percentage=$((100*$secondsCompleted/$inputlength))
        echo "$percentage"
        sleep 1
      done
      echo 100
    ) | zenity --progress --title="$appname" \
               --text="$progresstext" --auto-close
  else
    echo "$progresstext"
    while ps | grep "$pid " >/dev/null
    do
      percentage=`tail -c 90 "$mencoderlog" | \
                  cut -d"(" -f2 | cut -d")" -f1 | egrep [0-9]+%$`
      echo -ne "$percentage\r"
      sleep 1
    done
  fi
}

# sanity-check output directory
[ -d "$outputdir" ] || die "Can't find output directory $outputdir"

# get absolute path of output directory
outputdir=`cd "$outputdir" 2>/dev/null && pwd`

# sanity check helper apps
if [ $gui ]; then
  [ -z "$(which zenity)" ] && gui=
fi
[ -n "$(which mplayer)" ] || die 'mplayer not installed, see http://www.mplayerhq.hu/'
[ -n "$(which mencoder)" ] || die 'mencoder not installed, see http://www.mplayerhq.hu/'
if [ -z "$(mencoder -oac help | grep faac)" ]; then
  die 'mencoder can not encode AAC audio, please recompile with faac support'
fi
if [ -z "$(mencoder -ovc help | grep x264)" ]; then
  die 'mencoder can not encode H.264 video, please recompile with x264 support, see http://www.mplayerhq.hu/DOCS/HTML/en/video-codecs.html#codec-x264-encode'
fi
[ -n "$(which MP4Box)" ] || die 'MP4Box not installed, see http://gpac.sf.net/'

# trap signals so we can clean up our background processes and temp files
trap TrapBreak HUP INT TERM

if [ -f "$device" ]; then
  # input is file
  inputfile="$device"

  # check whether output file exists
  outputfile=`basename "$inputfile" .VOB`.mp4
  [ -s "$outputdir"/"$outputfile" ] && die "$outputdir/$outputfile already exists, will not overwrite"

  # forget tracks parameter so we don't get confused about it later
  tracks=

  # get video info
  videoinfo=`mplayer -identify -frames 0 -vc null -vo null -ao null -nosound \
             "$device" 2>&1`

  # get video length, truncated to the nearest second
  inputlength=`echo "$videoinfo" | \
               grep ^ID_LENGTH | \
               sed -e 's/^.*=//' -e 's/[.].*//'`
  [ -n "$inputlength" ] || die "Could not determine video length"
else
  # input is DVD device or directory containing VIDEO_TS
  [ -n "$(which lsdvd)" ] || die 'lsdvd not installed, see http://untrepid.com/acidrip/lsdvd.html'
  
  # gather some information about the disc
  discinfo=`lsdvd "$device" 2>/dev/null`
  longest=`echo "$discinfo" | grep '^Longest track: ' | sed 's/.*: 0*//'`

  # get disc title
  if [ -b "$device" ]; then
    # for physical discs, title is volume name
    disctitle=`echo "$discinfo" | \
               grep '^Disc Title:' | \
               sed -e 's/^.*://' -e 's/ //g'`
    [ -n "$disctitle" ] || die "No DVD found in $device"
  else
    # for folders, title is folder name
    # get absolute path so we can extract the actual folder name
    device=`cd "$device" 2>/dev/null && pwd`
    disctitle=`basename "$device"`
    # if folder is VIDEO_TS, we really want the parent folder
    if [ $disctitle = "VIDEO_TS" ]; then
      device=`cd "$device"/.. 2>/dev/null && pwd`
      disctitle=`basename "$device"`
    fi
  fi

  # remove whitespace from track list
  tracks=`echo "$tracks" | sed 's/\s//g'`

  # auto-encode single-track discs
  trackcount=`echo "$discinfo" | grep -c '^Title: '`
  if [ "$trackcount" = 1 ]; then
    # if there's only one track, auto-select it
    tracks=1
  fi

  # if no track number was specified, interactively ask which tracks to encode
  if [ -z "$tracks" ]; then
    if [ $gui ]; then
      tracks=`echo "$discinfo" | \
              grep '^Title: ' | \
              sed -e "s/Title: 0*$longest,/TRUE\n$longest,/" \
                  -e 's/Title: 0*/FALSE\n/' \
                  -e 's/, Length:/\nLength:/' | \
              zenity --list --checklist \
                     --title="$disctitle: Select tracks to encode" \
                     --width=700 --height=500 --separator="," \
                     --column="" --column="#" --column="Track information"`
    else
      echo "$disctitle"
      echo
      echo "$discinfo" | grep '^Title: ' | \
                         sed -e 's/Title: 0*//' \
                             -e 's/, Length/) Length/'
      echo
      echo -n "Tracks to encode (comma-separated): [$longest] "
      read tracks
      [ -z "$tracks" ] && tracks="$longest"
    fi

    # remove whitespace from track list (again)
    tracks=`echo "$tracks" | sed 's/\s//g'`
  fi
  
  # handle some special cases for tracks
  if [ "$tracks" = 'longest' ]; then
    # we already cached the longest track (but didn't verify it)
    tracks="$longest"
    [ -n "$tracks" ] || die "Could not find the longest track on $device"
  elif [ "$tracks" = 'all' ]; then
    # find all tracks on device
    tracks=`echo "$discinfo" | grep '^Title: ' | \
                               sed -e 's/^Title: 0*//' -e 's/,.*//'`
    # don't quote $tracks on next line, we want echo to collapse whitespace
    tracks=`echo $tracks | sed 's/ /,/g'`
  fi

  # if we don't have any tracks, just quit gracefully
  [ -z "$tracks" ] && exit 0
  
  # if multiple tracks were specified or found, get the first one
  track=`echo "$tracks" | cut -d"," -f 1`
  tracks=`echo "$tracks" | grep "," | cut -d"," -f 2-`

  # get track info
  videoinfo=`mplayer -identify -frames 0 -vc null -vo null -ao null \
             dvd://"$track" -dvd-device "$device" 2>&1`

  # get track length, truncated to the nearest second
  inputlength=`echo "$videoinfo" | \
               grep ^ID_DVD_TITLE_"$track"_LENGTH | \
               cut -d"=" -f 2 | \
               cut -d"." -f 1`
  [ -n "$inputlength" ] || die "Could not determine video length"

  if [ -b "$device" ]; then
    # For physical discs, try to detect and skip almost-0-length chapters.
    # These tend to show up in lsdvd output as "Length: 00:00:00.176"
    # and may indicate intentionally bad sectors on the disc.  Or not.
    # But even if they're just authoring cruft, there's no harm in excluding
    # them.
    if [ -z "$chapters" ]; then
      chapterinfo=`lsdvd -c -t"$track" 2>/dev/null`
      badchapters=`echo "$chapterinfo" | grep "Length: 00:00:00"`
      if [ -n "$badchapters" ]; then
        goodchapters=`echo "$chapterinfo" | grep "Chapter:" | grep -v "Length: 00:00:00" | sed -e "s/.*Chapter: //" -e "s/,.*//"`

        # if the entire track is just bogus chapters, exit gracefully
        [ -z "$goodchapters" ] && exit 0

        firstchapter=`echo "$goodchapters" | head -1 | sed -e "s/^0//"`
        lastchapter=`echo "$goodchapters" | tail -1 | sed -e "s/^0//"`
        if [ "$firstchapter" == "$lastchapter" ]; then
          chapters="$firstchapter"
        else
          chapters=`echo "$goodchapters" | head -1 | sed -e "s/^0//"`"-"`echo "$goodchapters" | tail -1 | sed -e "s/^0//"`
        fi
      fi
    fi
  fi

  # now we have enough information to construct the output filename
  # and check if it exists
  outputfile=`echo "$naming" | \
              sed -e "s/%d/$disctitle/g" \
                  -e "s/%t/\`printf \"%02d\" $track\`/g" \
                  -e  "s/%i/\`printf \"%02d\" $index\`/g"`.mp4
  [ -s "$outputdir"/"$outputfile" ] && die "$outputdir/$outputfile already exists, will not overwrite"

  # rip single track to temporary file
  tempfile=`mktemp -p "$scratchdir"` || \
            die "Could not copy video track to $scratchdir"
  inputfile="$tempfile".VOB
  mplayerlogfile="$inputfile".copy.log
  copytext="Copying track $track"
  [ -n "$chapters" ] && copytext="$copytext"", chapter $chapters"
  if [ $gui ]; then
    (
      echo
      while [ 1 ]; do sleep 1; done
    ) | zenity --progress --title="$appname" --text="$copytext" --pulsate &
    zenpid=$!
    # Run mplayer in the background and wait.  This way, if the user
    # clicks Cancel, we can immediately exit (via TrapBreak) without
    # waiting for mplayer to finish.
    mplayer dvd://"$track" -dvd-device "$device" "$chapters" -dumpstream \
            -dumpfile "$inputfile" 1>"$mplayerlogfile" 2>/dev/null &
    pid=$!
    wait $pid
    kill $zenpid
    zenpid=
  else
    echo "$copytext"
    if [ -z "$chapters" ]; then
      mplayer dvd://"$track" -dvd-device "$device" -dumpstream \
              -dumpfile "$inputfile" 1>"$mplayerlogfile" 2>/dev/null &
    else
      mplayer dvd://"$track" -dvd-device "$device" -chapter "$chapters" \
              -dumpstream -dumpfile "$inputfile" 1>"$mplayerlogfile" 2>/dev/null &
    fi
    pid=$!
    wait $pid
  fi
  pid=

  # if source is DVD device and this is the last track, eject the disc
  if [ -b "$device" ]; then
    if [ -z "$tracks" ]; then
      eject "$device" &
    fi
  fi
fi

# encode .vob to .mp4 (H.264/AAC)
avioutput="$scratchdir"/`basename "$inputfile" .VOB`.temp
mencoderlog="$scratchdir"/`basename "$inputfile" .VOB`.mencoder.log
mencoderpasslogfile="$scratchdir"/`basename "$inputfile" .VOB`.2pass.log

if [ -z "$crop" ]; then
  echo -ne "Auto-cropping..."
  crop=`mencoder -endpos 60 -ovc lavc -oac copy -o /dev/null -vf cropdetect "$inputfile" 2>/dev/null | grep CROP | awk -F"-vf crop=" {'print $2'} | cut -d")" -f 1 | uniq -c | sort -n | tail -n 1 | sed 's/^ *//' | cut -d" " -f 2`
fi
[ -z "$crop" ] && crop=720:480:0:0
if [ -n "$fitto4x3" ]; then
  aspectcode=`echo "$videoinfo" | grep ^VIDEO | grep aspect | awk -F"aspect " {'print $2'} | cut -d")" -f 1`
  if [ "$aspectcode" = "3" ]; then
    width=`echo "$crop" | cut -d":" -f1`
    height=`echo "$crop" | cut -d":" -f2`
    width=$(($height*9/8))
    crop="$width":"$height"
  fi
fi
echo "crop=$crop"

mencoder "$inputfile" -passlogfile "$mencoderpasslogfile" -o /dev/null -ovc x264 -x264encopts pass=1:bitrate="$videobitrate":"$x264encopts_required":"$x264encopts_optional":"$x264encopts" -vf pullup,softskip,crop="$crop",scale="$scale",harddup -oac faac -faacopts mpeg=4:br="$audiobitrate":object=2 -channels 2 -srate 48000 -ofps 24000/1001 >"$mencoderlog" 2>/dev/null &
pid=$!
pass=1
DisplayEncodingProgress
pid=

mencoder "$inputfile" -passlogfile "$mencoderpasslogfile" -o "$avioutput".avi -ovc x264 -x264encopts pass=2:bitrate="$videobitrate":"$x264encopts_required":"$x264encopts_optional":"$x264encopts" -vf pullup,softskip,crop="$crop",scale="$scale",harddup -oac faac -faacopts mpeg=4:br="$audiobitrate":object=2 -channels 2 -srate 48000 -ofps 24000/1001 >>"$mencoderlog" 2>/dev/null &
pid=$!
pass=2
DisplayEncodingProgress
pid=

echo "Creating $outputfile"
cd "$scratchdir"
MP4Box -aviraw video "$avioutput".avi >/dev/null
MP4Box -aviraw audio "$avioutput".avi >/dev/null
mv "$avioutput"_video.h264 "$avioutput".h264
mv "$avioutput"_audio.raw "$avioutput".aac
rm -f "$outputfile"
MP4Box -add "$avioutput".aac:lang=en "$outputfile" >/dev/null
MP4Box -add "$avioutput".h264:fps=23.976 "$outputfile" >/dev/null
[ -s "$outputfile" ] || die "Could not mux $outputfile"
mv "$outputfile" "$outputdir"/"$outputfile"
[ -s "$outputdir"/"$outputfile" ] || die "Could not create $outputdir/$outputfile"
cd - >/dev/null

CleanUpTempFiles

# if multiple tracks were specified, process the next one
if [ -n "$tracks" ]; then
  echo
  index=$(($index+1))
  exec "$0" -i "$index" -n "$naming" -o "$outputdir" -s "$scratchdir" \
       -t "$tracks" "$device"
fi
