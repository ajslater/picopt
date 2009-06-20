#!/usr/bin/tclsh

# $Id: pkgusage.tcl,v 1.35 2003/06/28 19:43:02 johan Exp $

#######################################################################
#
# pkgusage.tcl - 1.0.6
# Copyright (C) 2000-2003 Johan Walles - d92-jwa@nada.kth.se
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
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.
#
#######################################################################


#######################################################################
#
# INSTRUCTIONS
#
# To be able to execute this file:
# 1. Adjust the path to tclsh at the first line of this file.  If you
#  don't know where you have it, try /usr/bin/tclsh,
#  /usr/local/bin/tclsh, /usr/bin/tcl, /usr/local/bin/tcl, or do
#  'which tclsh' or 'which tcl' to locate it.
# 2. Mark this script as executable by doing 'chmod a+x pkgusage.tcl'
#
# This program is a tool to list all packages installed on system
# together with how many days ago any of the contents was last accessed.
# Packages with no stat()able files get an age of -1.  To clean out
# your harddrive, run the program and remove all packages with high
# numbers in front of them.
#
# Example: Try "./pkgusage.tcl | sort -n | less" or if that doesn't
#         work, "/usr/local/bin/tcl pkgusage.tcl | sort -n" from the
#         command line.
#
# Tip: If you get lots of warnings about non-statable files, try
#     running the program as root.
#
#######################################################################


#######################################################################
#
# To port this to some other package tool:
# ----------------------------------------
# * Write procs xxx_what_depends_on, xxx_list_files and
#  xxx_list_packages for your favourite package tool.  For help on
#  what these functions should do, check the corresponding rpm_*
#  functions below.
# * Verify that it works on your system.
# * Done!  Send the modified code to Johan, d92-jwa@nada.kth.se.
#
#######################################################################


#######################################################################
#
# Author: Johan Walles, d92-jwa@nada.kth.se, January 23, 2000
#
# Enhanced with dependency checking on January 29, 2000
#
# Split all RPM dependant parts out into functions to ease porting to
# other package tools on January 30, 2000
#
# Removed TclX dependency on Feb 12 2000
#   (thanks to Charles Thayer <thayer@mediabridge.com>)
#
# Fixed RPM name extraction on Feb 12 2000
#   (thanks to Alex Butcher <alex@cocoa.demon.co.uk>)
#
# Excluded links from date checking on Feb 12 2000
#
# Made the program work on versionless RPM names on Feb 13 2000.
#   (thanks to Adam Wendt <billyjoeray@netzero.net>,
#              Jim Nicholson <jimn@minusen.force9.co.uk>,
#              Alex Butcher <alex@cocoa.demon.co.uk>)
#
# Added dpkg support and automatic package tool selection on Feb 10,
# 2001.
#
# Fixed a file listing bug on Debian and cleaned out lots of unnecessary
# output on Aug 5 2001.
#
# Fixed a dpkg dependency resolution bug on Jan 21 2002.
#
# More or less around Jun 28 2003:  Lots of re-factoring.  Several
# Debian-specific bugs fixed.  Major speed-ups on Debian.  Progress
# meter now shows actual progress, and not just from the first stage.
# Limit age checking to binaries (if availabe) so that man database
# updates and the likes don't update package ages.
#
#######################################################################


#######################################################################
#
# TODO:
#
# Debian packages can have circular dependencies.  This needs to be
# supported by the dependency resolution code.  A suitable cycle
# detection algorithm may be found somewhere around
# "http://dmawww.epfl.ch/roso.mosaic/kf/enum/comb/node13.html"
#
#######################################################################


#
# RPM dependent procs
#

proc rpm_what_depends_on { package_name } {
    # Returns a list of all RPMs depending on package_name
    
    # Find out what capabilities this package provides
    set provides [exec rpm -q --provides $package_name]
    set provides_list [split $provides \n]

    # Find out what files this package provides
    set provides_files [exec rpm -ql $package_name]
    set provides_files_list [split $provides_files \n]
    # Append the provides_files_list to provides_list
    set provides_list [concat $provides_list $provides_files_list]
    
    # RPM gives some superfluous spaces with --provides.  Nuke 'em.
    regsub -all {[\{\}]} $provides_list {} provides_list
    while { [regsub -all {  } $provides_list { } provides_list] } {}

    # Extract the name (minus the version) of this package
    set name_only [exec rpm -q --queryformat %{NAME}\n $package_name]

    # The package provides itself
    lappend provides_list $name_only
	
    set depends_on_list []

    # Find out which packages depends on capabilities provided by
    # this package
    foreach capability $provides_list {
	if { [catch { exec rpm -q --whatrequires $capability --queryformat %{NAME}\n 2> /dev/null } depends_on_me] != 0 } {
	    set depends_on_me ""
	}
	set depends_on_list [concat $depends_on_list [split $depends_on_me \n]]
    }

    return $depends_on_list
}

proc rpm_list_files { package_name } {
    # Returns a list of all files in package_name
    
    # Fetch the names of all files in the package
    set fileliststring [exec rpm -ql $package_name]

    # FIXME: RPM should report "no files" to stderr, but it does so to
    # stdout :-(
    if { $fileliststring == "(contains no files)" } {
	set fileliststring {}
    }

    # Put the filenames in a list
    set filelist [split $fileliststring \n]

    return $filelist
}

proc rpm_list_packages { } {
    # Returs a list of the names of all installed packages
    
    return  [split [exec rpm -qa --queryformat %{NAME}\n] \n]
}

#
# Dpkg dependent procs
#

proc dpkg_what_depends_on { package_name } {
    # Returns a list of all debs depending on package_name

    set returnme {}

    # Find out what this package provides

    # FIXME: Isn't there some way of calling dpkg for listing
    # everything currently installed that depends on a specific
    # package?  The below solution doesn't feel very portable.

    # This package provides itself
    set provides_list [list $package_name]

    # This package also provides anything that is listed on a
    # "Provides: " line
    catch {
        set provides_list [concat $provides_list [split [exec grep -A10 "Package: $package_name" /var/lib/dpkg/status | grep "Provides: " | cut -c 11- | sed 's/,//g'] " "]]
    }

    set depends_on_list []
    
    # For each thing that this package provides...
    foreach current_provided $provides_list {
        # ... add the packages that depend on it to the return value
	set depends_on_me ""
        catch {
            set depends_on_me [split [exec egrep -B 10 "^Depends:.* $current_provided\(\(\[, \]\)|\$\)" /var/lib/dpkg/status | grep -B 1 "^Status: install ok installed" | grep "^Package: " | cut -c 10-] \n]
        }

	set depends_on_list [concat $depends_on_list $depends_on_me]
    }
    
    return $depends_on_list
}

proc dpkg_list_files { package_name } {
    # Returns a list of all files in package_name

    # Fetch the names of all files in the package
    set fileliststring [exec bash -c "cat /var/lib/dpkg/info/$package_name.list"]

    # Put the filenames in a list
    set filelist [split $fileliststring \n]

    return $filelist
}

proc dpkg_list_packages { } {
    # Returs a list of the names of all installed packages

    # FIXME: Isn't there some way of calling dpkg for listing all the
    # installed files without tons of decorations?  This solution
    # doesn't feel very portable.
    return  [split [exec grep -B1 "^Status: install ok installed" /var/lib/dpkg/status | grep "^Package: " | cut -c 10-] \n]
}

#
# Package tool independent procs
#

proc get_n_done_packages { } {
    global censored_package_age

    return [array size censored_package_age]
}

proc get_censored_package_age { package_name age } {
    # Adjust the age so that no package is reported to be older than
    # any package that depends on it

    global package_tool
    global censored_package_age

    if { ! [info exists censored_package_age($package_name)] } {

	set depends_on_list [[set package_tool]_what_depends_on $package_name]
	
	set censored_package_age($package_name) $age
	
	if { [llength $depends_on_list] != 0 } then {
	    foreach depending_package $depends_on_list {

		set depending_package_age \
		    [get_censored_package_age $depending_package \
			 [get_raw_package_age $depending_package]]

		if { $depending_package_age < $age } {
		    set age $depending_package_age
		}
	    }
	}

	set censored_package_age($package_name) $age
    }

    return $censored_package_age($package_name)
}

proc measure_files_age { packagename filelist } {
    set now [clock seconds]
    set lastuse "DONTKNOW"
    
    # Go through all files of the package
    foreach filename $filelist {
	# If the file is accessible...
	if { [statable $filename] } then {
            if { ! [ignorable $filename] } then {
                file lstat $filename filestat
                set use $filestat(atime)

                if { ($use - 600) > $now } {
                    # Warn about files last accessed more than ten minutes
                    # into the future
                    puts stderr "Warning: $filename of $packagename has access time in the future"
                }
	    
                # Check when it was last used
                if { $lastuse == "DONTKNOW" ||
		     $use > $lastuse } then {
                    set lastuse $use
                }
            }
	} else {
            puts stderr "Warning: Couldn't stat file \"$filename\" of $packagename"
        }
    }
    
    if { $lastuse == "DONTKNOW" } then {
	return "DONTKNOW"
    }
    
    # If any of the files were last accessed in the future...
    if { $lastuse > $now } then {
	# ... assume it is current.
	set lastuse $now
    }

    return [expr ($now - $lastuse) / 86400]
}

proc binsandlibs_only { filelist } {
    # Create a new list of filenames containing only the files under a
    # /bin/, a /sbin/ or a /lib/ directory
    
    set return_me []
    
    foreach filename $filelist {
	if { [regexp -- "((/lib/)|(/sbin/)|(/bin/)|(/games/))\[^/]*$" $filename] } {
	    lappend return_me $filename
	}
    }
    
    return $return_me
}

proc get_raw_package_age { package_name } {
    global package_tool
    global raw_package_age

    if { [info exists raw_package_age($package_name)] } {
	return $raw_package_age($package_name)
    }
    
    set filelist [[set package_tool]_list_files $package_name]

    # First, age-check only binaries and libraries
    set raw_age [measure_files_age $package_name [binsandlibs_only $filelist]]
    if { $raw_age != "DONTKNOW" } then {
	set raw_package_age($package_name) $raw_age
	return $raw_age
    }
    
    # That didn't work, try all of the files in the package...
    set raw_age [measure_files_age $package_name $filelist]
    if { $raw_age == "DONTKNOW" } then {
	puts stderr "Warning: Couldn't stat() any files of package $package_name"
	
	# ... assume it is newer than current.
	set raw_package_age($package_name) $raw_age
	return $raw_age
    }
    
    set raw_package_age($package_name) $raw_age
    return $raw_age
}

proc statable { filename } {
    # Can we stat this file?

    if { $filename == "" } {
        return 0
    }

    # The exists test below will return false for broken symlinks, so
    # if we want symlinks to be stat:ed we have to check for those
    # here.
    set filetype "INACCESSIBLE"
    catch {
	set filetype [file type $filename]
    }
    if { $filetype == "link" } {
	return 1
    }
    
    if { $filetype == "INACCESSIBLE" } {
	return 0
    }
    
    return 1
}

proc ignorable { filename } {
    # Should we skip stat:ing this file?

    set filetype [file type $filename]
    set isdir [expr { $filetype == "directory" }]
    set islink [expr { $filetype == "link" }]
    
    return [expr $isdir || $islink]
}

proc set_package_tool { } {
    # Decide what packaging tool to use
    global package_tool

    # Find the candidates using introspection.  The candidates
    # are everything that has an xxx_list_packages function.
    set list_packages_functions [info procs *_list_packages]

    set max_packages 0
    set best_listing_function INTERNAL_ERROR_
    # For each candidate...
    foreach current_listing_function $list_packages_functions {
        # ... find out how many such packages are installed...
        set current_packages 0
        if { [catch { set current_packages [llength [$current_listing_function]]}] } {
            set current_packages 0
        }

        # ... and select the one with most packages
        if { $current_packages > $max_packages } {
            set best_listing_function $current_listing_function
            set max_packages $current_packages
        }
    }

    if { $max_packages <= 0 } {
        puts stderr "Error: None of the supported package managers seems to have any packages installed!"
        exit 1
    }

    # Convert the name of the best listing function into a
    # packaging tool name
    regsub _list_packages $best_listing_function {} package_tool
    
    puts stderr "Note: $package_tool packaging system selected"
}

#
# Main program
#

# Decide what package manager we should use
set_package_tool

# Fetch the names of all packages
set package_list [[set package_tool]_list_packages]

set n_packages [llength $package_list]
puts stderr "Calculating ages of $n_packages packages..."

# Go through all packages to check their ages
set last_user_report [clock seconds]
set packages_done 0
foreach package_name $package_list {
    # Tell the user how we're doing every four seconds
    if { [expr [clock seconds] - 3 ] > $last_user_report } {
	puts stderr "[expr (100 * [get_n_done_packages]) / $n_packages]% done..."
	set last_user_report [clock seconds]
    }
    
    puts stdout "[get_censored_package_age $package_name [get_raw_package_age $package_name]] $package_name"
    incr packages_done
}
