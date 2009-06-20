#!/bin/bash
IFS=$'\n'
export SOURCE=Pictures
export DEST=iPhone
export SIZE=320x480


cd $HOME
files=`find ${SOURCE} \( -iname "*.jpg" -or -iname "*.jpeg"  -or -iname "*.png" -or -iname "*.gif" \) -and -not -wholename "*/Wallpaper*" -and -not -wholename "*/.*"`
for j in $files; do
        oldsize=`identify -q "$j" | awk '{ print $3 }'`
        #TODO logic for x-y picture proportions
        oldx=${oldsize%%x*}
        oldy=${oldsize##*x}
        if[[ $oldx -gt $oldy ]]; then
            if[[ $oldx > 480 ]]; then
                size=480x320
            else
                size=$oldsize
            fi
        else
            if[[ $oldy > 480 ]]; then
                size=320x480
            else
                size=$oldsize
            fi
        fi

        dir=`dirname "$j"`
        mkdir -p "$HOME/$DEST/$dir"
        base="${j%%\.*}"
        suff="${j##*\.}"
        outfile="${DEST}/${base}-${size}.${suff}"
        if [[ ! -f "$outfile" ]]; then
            convert -size $size -resize $size +profile "*" "${j}" "${outfile}"
        fi;
done;
