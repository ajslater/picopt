#!/usr/bin/python -OO 
"""
Runs pictures through image specific external optimizers
"""
__revision__ = '0.2.0'
# Need du style summary at end
# Detect grayscale images and use flags for transorms


import os, optparse, Image, ImageFile, shutil
PNG_EXT = '.png'
MNG_EXT = '.mng'
JPEG_EXT = '.jpg'
BACKUP_EXT = '.bak'
JPEGTRAN_ARGS = ['jpegtran', '-optimize', '-outfile']
CONVERT_ARGS = ['convert', '-quality', '100']
PNGCRUSH_ARGS = ['pngcrush', '-brute', '-cc', '-fix', '-l 9', '-max 524288',
                 '-q']
DU_ARGS = ['du', '--human-readable', '--summarize']
PNG_FORMAT = 'PNG'
GIF_FORMAT = 'GIF'
TIFF_FORMAT = 'TIFF'
JPEG_FORMAT = 'JPEG'
OPTIMIZABLE_FORMATS = [PNG_FORMAT, GIF_FORMAT, JPEG_FORMAT, TIFF_FORMAT]
FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'

def get_options_and_arguments() :
    """parses the command line"""
    usage = "usage: %prog [options] [image files]\npicopt requires" \
    "that (ImageMagick)convert, optiping and jpegtran-mmx be on\nthe" \
    "path. Why? Because there's no pythonMagick in Debian and PIL" \
    " sucks."
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--keepBackup", action="store_true", 
        dest="backup", default=0, 
    help="Keep backup files of the original image")
    parser.add_option("-d", "--dir", action="store", dest="dir", 
        default=os.getcwd(), 
    help="Directory to change to before optimiziaton")
    parser.add_option("-f", "--formats", action="store", dest="formats",
        default=DEFAULT_FORMATS, 
    help="Only optimize images of the specifed '" \
    +FORMAT_DELIMETER+"' delimited formats")
    parser.add_option("-r", "--recurse", action="store_true", 
        dest="recurse", default=0, help="Recurse down through " \
    "directories ignoring the image file arguments on the " \
    "command line")
    parser.add_option("-q", "--quiet", action="store_false", 
        dest="verbose", default=1, help="Do not display output")

    (options, arguments) = parser.parse_args()

    if options.formats == DEFAULT_FORMATS :
        options.formats = OPTIMIZABLE_FORMATS
    else :
        options.formats = options.formats.split(FORMAT_DELIMETER)
    arguments.sort()

    return (options, arguments)


def replace_ext(filename, new_ext) :
    """replaces the file extention"""
    dot_index = filename.rfind('.')
    new_filename = filename[0:dot_index]+new_ext
    return new_filename


def report_percent_saved(size_in, size_out) :
    """spits out how much space the optimazation saved"""
    if size_in <= size_out :
        print('\boptimization didn\'t shrink the file.')
    else :
        percent_saved = str((1 - (float(size_out) / float(size_in))) * 100)+'%'
        size_in_kb = str(size_in / 1024)+'kB'
        size_out_kb = str(size_out / 1024)+'kB'
        print(size_in_kb, '-->', size_out_kb, 'saved', percent_saved)


def get_image_info(filename, options) :
    """returns the image's format"""
    try :
        image = Image.open(filename)
        bad_image = image.verify()
        image_format = image.format
        sequenced = is_image_sequenced(image)
        if image_format in options.formats :
            print(filename, image.format, image.mode+' ')
    except Exception :
        bad_image = 1
        image_format = 'NONE'
        sequenced = 0

    return (bad_image, image_format, sequenced)


def spawn(args) :
    """spawns a system program, should be moved to an outside lib"""
    os.spawnvp(os.P_WAIT, args[0], args)


def convert_to_lossless(filename, backup_filename, sequenced, options) :
    """converts lossless images into PNG or MNG"""
    if sequenced :
        ext = MNG_EXT
    else :
        ext = PNG_EXT

    new_filename = convert_to_ext(filename, backup_filename, ext, options)

    return new_filename


def is_image_sequenced(image) :
    """determines if the image is a sequenced image"""
    try :
        image.seek(1)
        result = 1
    except EOFError :
        result = 0

    return result


def pngcrush(filename, backup_filename, options) :
    """runs the EXTERNAL program optipng on the file"""
    args = PNGCRUSH_ARGS+[backup_filename, filename]
    if options.verbose :
        print('\tOptimizing PNG...',)
    spawn(args)

    # Special cleanup, I don't know why this happens.
    if os.path.isfile('pngout.png') :
        os.remove('pngout.png')
    
    return filename


def jpegtran(filename, backup_filename, options) :
    """runs the EXTERNAL program jpegtran on the file"""
    args = JPEGTRAN_ARGS+[filename, backup_filename]
    if options.verbose :
        print('\tOptimizing JPEG...',)
    spawn(args)
    return filename     


def convert_to_ext(filename, backup_filename, ext, options) :
    """converts a file to the given extention type"""
    new_filename = replace_ext(filename, ext)
  
    args = CONVERT_ARGS+[backup_filename, new_filename]
    if options.verbose :
        print('\tConverting to', ext+'...',)
    spawn(args)

    if ext == JPEG_EXT or ext == PNG_EXT :
     
        # Do this quietly, so as not to fuck up the output
        if options.verbose :
            import copy
            silent_options = copy.copy(options)
            silent_options.verbose = 0
        else :
            silent_options = options

        if options.verbose :
            print("\boptimizing:",)
        optimize_image(new_filename, silent_options)
        print('\t',)

    if os.path.isfile(new_filename) and not options.backup :
        os.remove(filename)
  
    return new_filename


def recover_file(backup_filename, new_filename, options) :
    """recover the original version of a file that did not optimize 
    well"""
    try :
        if options.verbose :
            print('\tImage could not be optimized, so I am restoring it from '\
                    ' backup...')

        unbackedup_filename = replace_ext(backup_filename, '')
        os.remove(new_filename)
        os.rename(backup_filename, unbackedup_filename)
        if options.verbose :
            print('\bdone.')
    except Exception as why:
        print(why)


def is_format_selected(image_format, formats, options) :
    """returns a boolean indicating weather or not the image format
    was selected by the command line options"""
    result = image_format in formats and image_format in options.formats
    return result

def clean_up_after_optimize(new_filename, backup_filename, 
    filesize_in, options):
    """clean up the backups, recover from backup if optimization was bad
    and report on how much we saved"""
    if new_filename != -1 :
        try :
            filesize_out = os.stat(new_filename).st_size
            if options.verbose :
                report_percent_saved(filesize_in, filesize_out)
 
            if (filesize_out > 0) and (filesize_out < filesize_in) :
                if not options.backup :
                    try :
                        os.remove(backup_filename)
                    except OSError:
                        pass
            else :
                recover_file(backup_filename, new_filename, options)
        except OSError :
            recover_file(backup_filename, new_filename, options)
    

def optimize_image(filename, options) :
    """optimizes a given image from a filename"""
    (bad_image, image_format, sequenced) = get_image_info(filename, options)

    if not bad_image :
        filesize_in = os.stat(filename).st_size
        backup_filename = os.path.normpath(filename+BACKUP_EXT)
        shutil.copy2(filename, backup_filename)
     
        if is_format_selected(image_format, [PNG_FORMAT], options) :
            new_filename = pngcrush(filename, backup_filename, options)
        elif is_format_selected(image_format, [JPEG_FORMAT], options) :
            new_filename = jpegtran(filename, backup_filename, options)
        elif is_format_selected(image_format, [GIF_FORMAT, TIFF_FORMAT],
        options) :
            new_filename = convert_to_lossless(filename, backup_filename,
            sequenced, options)
        else :
            new_filename = -1
            if options.verbose :
                pass
        
        clean_up_after_optimize(new_filename, backup_filename,
                            filesize_in, options)
   
    else :
        print(filename,'has an unrecognizable input format.')


def optimize_files(cwd, filter_list, options) :
    """sorts through a list of files, decends directories and
       calls the optimizer on the extant files"""
    for filename in filter_list :
        filename_full = os.path.normpath(cwd+os.sep+filename)
        if os.path.isdir(filename_full) :
            if options.recurse :
                next_dir_list = os.listdir(filename_full)
                next_dir_list.sort()
                optimize_files(filename_full, next_dir_list, options)
        elif os.path.exists(filename_full) :
            optimize_image(filename_full, options)
        else :
            if options.verbose :
                print(filename,'was not found.')


def main() :
    """main"""    
    ImageFile.MAXBLOCK = 3000000 # default is 64k
    (options, arguments) = get_options_and_arguments()   
 
    os.chdir(options.dir)
    cwd = os.getcwd()
  
    if options.recurse :
        filter_list = os.listdir(cwd)
        filter_list.sort()
    else :
        filter_list = arguments
  
    optimize_files(cwd, filter_list, options)


if __name__ == '__main__':
    main()
