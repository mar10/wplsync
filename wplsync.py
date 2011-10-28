# (c) 2011 Martin Wendt; see http://tabfix.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Synchronize Media Playlists with a target folder.

- ...

http://lifehacker.com/231476/alpha-geek-whip-your-mp3-library-into-shape-part-ii-+-album-art

TODO:
- check max path length 256
- print and check max size (16GB)
- remove empty folders (except for album art)
- sync Album Art "Folder.jpg" or "AlbumArtSmall.jpg". 
  ??? Also display album "AlbumArt_WMID_Large.jpg" or "AlbumArt_WMID_Small.jpg"

 
Project home: http://tabfix.googlecode.com/  
"""
from optparse import OptionParser
import os
from fnmatch import fnmatch
from xml.etree import ElementTree as ET
from _version import __version__
import filecmp
import shutil


DEFAULT_OPTS = {
    "copy_extensions": ["mp3", ],
    "copy_files": ["Folder.jpg", "AlbumArtSmall.jpg"],
}


def create_info_dict():
    res = {"root_folder": None,
           "file_list": [], # absolute paths
           "file_map": {}, # key: rel_path, value: {}
           "error_files": [],
           "skip_count": 0,
           "process_count": 0,
           "error_count": 0
          }
    return res


def add_file_info(opts, info_dict, fspec):
    assert os.path.isabs(fspec)
    info_dict["process_count"] += 1
    # Get path relative to the synced folder
    rel_path = os.path.relpath(fspec, info_dict["root_folder"])
#    print "rel_path=", rel_path

    if not fnmatch(fspec, "*.mp3"):
        info_dict["skip_count"] += 1
        if opts.verbose >= 2:
            print "skipping %s" % fspec
    elif not os.path.isfile(fspec):
        info_dict["skip_count"] += 1
        info_dict["error_count"] += 1
        if opts.verbose >= 1:
            print "File not found: '%s'" % fspec
    else:
        info_dict["file_list"].append(fspec)
        size = os.path.getsize(fspec)
        modified = os.path.getmtime(fspec)
        created = os.path.getctime(fspec)
        info = {"fspec": fspec,
                "rel_path": rel_path,
                "size": size,
                "modified": modified,
                "created": created}
        info_dict["file_map"][rel_path] = info
        return True
    return False


def read_folder_files(opts, folder_path, is_target):
    if opts.verbose >= 1:
        print 'Reading folder %s...' % (folder_path, )
    res = create_info_dict()
    if is_target:
        res["root_folder"] = opts.target_folder
    else:
        res["root_folder"] = opts.source_folder
    for dirname, dirnames, filenames in os.walk(folder_path):
#        for subdirname in dirnames:
#            print os.path.join(dirname, subdirname)
        for filename in filenames:
            fspec = os.path.join(dirname, filename)
            add_file_info(opts, res, fspec)
    return res


def read_playlist_wpl(opts, playlist_path, info):
    """Read a WPL playlist and add file info to dictionary."""
    # TODO: this assert may be removed
    assert playlist_path.startswith(opts.source_folder)
    assert os.path.isabs(playlist_path)
    
    if opts.verbose >= 1:
        print 'Parsing playlist "%s"...' % (playlist_path, )
    tree = ET.parse(playlist_path)
    
    try:
        generator  = tree.find("head/meta[@name='Generator']").attrib["content"]
    except SyntaxError:
        generator  = None # requires ElementTree 1.3+
    title = tree.find('head/title').text
    if opts.verbose >= 1:
        print 'Scanning playlist "%s" (%s)...' % (title, generator)
    playlist_folder = os.path.dirname(playlist_path)
    for media in tree.find("body/seq"):
        fspec = media.attrib["src"]
        # If the fspec was given relative, it is relative to the playlist
        if not os.path.isabs(fspec):
            fspec = os.path.join(playlist_folder, fspec)
            fspec = os.path.normcase(os.path.normpath(os.path.abspath(fspec)))
        add_file_info(opts, info, fspec)
    # TODO: faster sequential approach:
    # iparse = ET.iterparse(playlist_path, ["end", ])
    # for event, elem in iparse:
    #     if event == "end" and elem.tag == "media":
    #         print elem.attrib["src"]
    return


def read_source_files(opts):
    """Read source files (either complete folder or using given playlists)."""
    res = create_info_dict()
    res["root_folder"] = opts.source_folder
    if len(opts.playlist_paths) == 0:
        read_folder_files(opts, opts.source_folder)
    else:
        for pl in opts.playlist_paths:
            read_playlist_wpl(opts, pl, res)
    return res


def copy_file(opts, src, dest):
    assert os.path.isfile(src)
    if opts.verbose >= 1:
        print 'Copy: %s' % dest
    dir = os.path.dirname(dest)
    if not os.path.exists(dir):
        os.makedirs(dir)
    shutil.copy2(src, dest)

        
def sync_file_lists(opts, source_map, target_map):
    """Unify leading spaces and tabs and strip trailing whitespace.
    
    """
    # Pass 1: find orphans
    orphans = []
    for rel_path, target_info in target_map["file_map"].iteritems():
        src_info = source_map["file_map"].get(rel_path)
        if not src_info:
            # Removed
            if opts.verbose >= 1:
                print 'REMOVED: %s' % rel_path
            orphans.append(target_info)
    # Pass 2: copy files
    match_count = 0
    match_count2 = 0
    for rel_path, src_info in source_map["file_map"].iteritems():
        target_info = target_map["file_map"].get(rel_path)
        if target_info:
            match_count += 1
            if filecmp.cmp(src_info["fspec"], target_info["fspec"], shallow=True):
                # Identical
                match_count2 += 1
                if opts.verbose >= 2:
                    print 'IDENTICAL: %s' % rel_path
            else:
                # Modified
                if opts.verbose >= 1:
                    print 'MODIFIED: %s' % rel_path
                shutil.copy2(src_info["fspec"], target_info["fspec"])
        else:
            # New
            if opts.verbose >= 1:
                print 'NEW: %s' % rel_path
                target_fspec = os.path.join(opts.target_folder, rel_path)
#                print 'copy2: %s' % target_fspec
#            shutil.copy2(src_info["fspec"], target_fspec)
            copy_file(opts, src_info["fspec"], target_fspec)

    if opts.verbose >= 1:
        print 'Found %s matches, %s identical, %s orphans' % (match_count, match_count2, len(orphans))

    # Pass 2: remove
    if opts.delete_orphans:
        pass



def run():
    # Create option parser for common and custom options
    parser = OptionParser(prog="plsync", # Otherwise 'plsync-script.py' gets displayed
                          version=__version__,
                          usage="usage: %prog [options] SOURCE_FOLDER TARGET_FOLDER [PLAYLIST [, PLAYLIST...]]",
                          description="Synchronize two media folders, optionally filtered by playlists.",
                          epilog="See also http://tabfix.googlecode.com")

    parser.add_option("-x", "--execute",
                      action="store_false", dest="dry_run", default=True,
                      help="turn off the dry-run mode (which is ON by default), " 
                      "that would just print status messages but does not change "
                      "anything")
    parser.add_option("-q", "--quiet",
                      action="store_const", const=0, dest="verbose", 
                      help="don't print status messages to stdout (verbosity 0)")
    parser.add_option("-v", "--verbose",
                      action="count", dest="verbose", default=1,
                      help="increment verbosity to 2 (use -vv for 3, ...)")
#    parser.add_option("", "--ignore-errors",
#                      action="store_true", dest="ignoreErrors", default=False,
#                      help="ignore errors during processing")
    parser.add_option("-c", "--copy-playlists",
                      action="store_true", dest="copy_playlists", default=False,
                      help="also copy all playlists that are passed as arguments")
    parser.add_option("-d", "--delete",
                      action="store_true", dest="delete_orphans", default=False,
                      help="delete target files that don't exist in PLAYLIST")
    parser.add_option("-e", "--allow-externals",
                      action="store_true", dest="include_externals", default=False,
                      help="allow source files outside SOURCE_FOLDER and copy them to TAGRGET_FOLDER/external. "
                      "Note that the target playlists may not work as axpected in this case.")
    
    # Parse command line
    (options, args) = parser.parse_args()

    # if len(args) == 0:
    #     args = ["/Users/martin/prj/plsync/sample.wpl",
    #             "/Users/martin/prj/plsync/test"]

    if len(args) < 1:
        parser.error("missing required SOURCE_FOLDER")
    elif len(args) < 2:
        parser.error("missing required TARGET_FOLDER")
    elif not os.path.isdir(args[0]):
        parser.error("SOURCE_FOLDER must be a folder")
    elif not os.path.isdir(args[1]):
        parser.error("TARGET_FOLDER must be a folder")

    options.source_folder = os.path.normcase(os.path.normpath(os.path.abspath(args[0])))
    options.target_folder = os.path.normcase(os.path.normpath(os.path.abspath(args[1])))

    options.playlist_paths = []
    for pl in args[2:]:
        pl = os.path.normcase(os.path.normpath(os.path.abspath(pl)))
        if not os.path.isfile(pl):
            parser.error("'%s' must be a playlist file" % pl)
        options.playlist_paths.append(pl)

    # Call processor
    source_info = read_source_files(options)
    target_info = read_folder_files(options, options.target_folder, True)

    if options.verbose >= 1:
        print "Source: %s files, %s valid" % (source_info["process_count"],
                                              len(source_info["file_list"])
                                              )
        print "Target: %s files, %s valid" % (target_info["process_count"],
                                              len(target_info["file_list"])
                                              )

    sync_file_lists(options, source_info, target_info)
    
    if options.dry_run and options.verbose >= 1:
        print("\n*** Dry-run mode: no files have been modified!\n"
              "*** Use -x or --execute to process files.")


if __name__ == "__main__":
    run()
