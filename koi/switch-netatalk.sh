#!/bin/sh
CONF=$1
AFP_CONF=/etc/netatalk/AppleVolumes.default
cp ${AFP_CONF}.${CONF} ${AFP_CONF}
/etc/init.d/netatalk restart
