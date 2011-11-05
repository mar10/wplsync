# (c) 2011 Martin Wendt; see http://wplsync.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Synchronize Media Playlists with a target folder.

- ...

http://lifehacker.com/231476/alpha-geek-whip-your-mp3-library-into-shape-part-ii-+-album-art

TODO:
- check max path length 256
- print and check max size (16GB)
- sync Album Art "Folder.jpg" or "AlbumArtSmall.jpg". 
  ??? Also display album "AlbumArt_WMID_Large.jpg" or "AlbumArt_WMID_Small.jpg"
- '-i' ignore errors
- '-f' force-update, even if target is newer
 
Project home: http://wplsync.googlecode.com/  
"""
from optparse import OptionParser
import os
from fnmatch import fnmatch
from xml.etree import ElementTree as ET
from _version import __version__
import filecmp
import shutil
import time
import sys


DEFAULT_OPTS = {
    # fnmatch patterns (see http://docs.python.org/library/fnmatch.html)
    # Media files that will be synced
    "media_file_patterns": ["*.aif",
                            "*.m3u",
                            "*.m4a",
                            "*.m4p",                            
                            "*.mp3",
                            "*.mpa",
                            "*.oga",
                            "*.ogg",
                            "*.pcast",
                            "*.ra",
                            "*.wav", 
                            "*.wma",
                            ],
    # Other files that will be synced, but removed if target folder is otherwise
    # empty
    "copy_file_patterns": ["Folder.jpg", 
                           "AlbumArtSmall.jpg",
                           ],
    # Temporary files, that can savely be deleted in target folders
    "transient_file_patterns": [".DS_Store",
                                "desktop.ini",
                                "Thumbs.db",
                                ],
}

SYNC_FILE_PATTERNS = DEFAULT_OPTS["media_file_patterns"] + DEFAULT_OPTS["copy_file_patterns"]
PURGE_FILE_PATTERNS = DEFAULT_OPTS["transient_file_patterns"] + DEFAULT_OPTS["copy_file_patterns"]

def create_info_dict():
    res = {"root_folder": None,
           "file_list": [], # relative paths, ordered by scan occurence
           "file_map": {}, # key: rel_path, value: info_dict
           "folder_map": {}, # key: re_path, value: True
           "byte_count": 0,
           "ext_map": {},
#           "unhandled_ext_map": {},
           "error_files": [],
           "skip_count": 0,
           "process_count": 0,
           "error_count": 0
          }
    return res


def canonical_path(p):
    res = os.path.normcase(os.path.normpath(os.path.abspath(p)))
    return res


def check_path_independent(p1, p2):
    """Return True if p1 and p2 don't overlap."""
    p1 = canonical_path(p1) + "/"
    p2 = canonical_path(p2) + "/"
    return not (p1.startswith(p2) or p2.startswith(p1)) 


def match_pattern(fspec, patterns):
    """Return True, if fspec matches at least on pattern in the list."""
    for pat in patterns:
        if fnmatch(fspec, pat):
            return True
    return False

    
def copy_file(opts, src, dest):
    assert os.path.isfile(src)
    assert not dest.startswith(opts.source_folder) # Never change the source folder

#    if opts.verbose >= 2:
#        print 'Copy: %s' % dest
    dir = os.path.dirname(dest)
    if not opts.dry_run:
        if not os.path.exists(dir):
            os.makedirs(dir)
        shutil.copy2(src, dest)
    return

        
def delete_file(opts, fspec):
    assert os.path.isfile(fspec)
    assert opts.delete_orphans
    assert not fspec.startswith(opts.source_folder) # Never change the source folder
#    if opts.verbose >= 2:
#        print 'Delete: %s' % dest
    if not opts.dry_run:
        os.remove(fspec)
    return

        
def purge_folders(opts, target_map):
    """Delete all child folders that are ampty or only contan transient files."""
    root_folder = target_map["root_folder"]
    assert os.path.isdir(root_folder)
    assert opts.delete_orphans
    assert not root_folder.startswith(opts.source_folder) # Never change the source folder
    if opts.verbose >= 1:
        print "Purge folders in %s ..." % root_folder
    # visit 

    if len(target_map["file_list"]) == 0:
        print("The target folder does not contain media files. "
              "This could result in removing the complete root_folder; aborted.")
        return

    purge_folders = []
    for folder, subfolders, filenames in os.walk(root_folder):
        # Check if this folder contains non-transient files
        can_purge = True
        for filename in filenames:
            if not match_pattern(filename, PURGE_FILE_PATTERNS):
                can_purge = False
                break
        # If ONLY transient files are found, remove them.        
        if can_purge:
            for filename in filenames:
                fspec = os.path.join(folder, filename)
                if match_pattern(filename, PURGE_FILE_PATTERNS):
                    if opts.verbose >= 2:
                        print "Purge transient file %s" % fspec
                    delete_file(opts, fspec)
            # Add this folder to the purge list.
            # (We don't need to do this for parents, since os.removedirs will
            # get them anyway.)
            if len(subfolders) == 0:
                purge_folders.append(folder)
    # Now remove empty leaves and all parents (if they are empty then)
    for folder in purge_folders:
        if opts.verbose >= 1:
            print "Remove empty folder %s" % folder
        assert os.path.isdir(folder)
        assert not folder.startswith(opts.source_folder) # Never change the source folder
        if not opts.dry_run:
            os.removedirs(folder)
    return

        
def add_file_info(opts, info_dict, fspec):
    """Append fspec to info_dict, if it is a valid media file."""
    assert os.path.isabs(fspec)
    info_dict["process_count"] += 1
    # Get path relative to the synced folder
    ext = os.path.splitext(fspec)[-1].lower()

    if not os.path.isfile(fspec):
        # Playlist reference cannot be resolved
        info_dict["skip_count"] += 1
        info_dict["error_count"] += 1
        if opts.verbose >= 1:
            print "File not found: '%s'" % fspec
        return False

    rel_path = os.path.relpath(fspec, info_dict["root_folder"])
#    rel_folder_path = os.path.dirname(rel_path)
#    folder_path = os.path.dirname(fspec)
#    is_media_file = match_pattern(fspec, DEFAULT_OPTS["media_file_patterns"])
#    is_copy_file = match_pattern(fspec, DEFAULT_OPTS["copy_file_patterns"])
#    is_transient_file = match_pattern(fspec, DEFAULT_OPTS["transient_file_patterns"])

    # Record folder (mark as True if it contains at least one media file)
#    if is_media_file:
#        info_dict["folder_map"][folder_path] = True
#    elif not folder_path in info_dict["folder_map"]:
#        info_dict["folder_map"][folder_path] = False

    # Skip files with unsupported extensions
#    if not is_media_file and not is_copy_file:
    if match_pattern(fspec, SYNC_FILE_PATTERNS):
        info_dict["ext_map"][ext] = False
    else:
        info_dict["ext_map"][ext] = True
        info_dict["skip_count"] += 1
        if opts.verbose >= 3:
            print "Skipping %s" % fspec
        return False

    # Copy media files (and album art, ...)
    info_dict["file_list"].append(rel_path)
    size = os.path.getsize(fspec)
#        modified = os.path.getmtime(fspec)
#        created = os.path.getctime(fspec)
    info = {"fspec": fspec,
            "rel_path": rel_path,
            "size": size,
#                "modified": modified,
#                "created": created,
            }
    info_dict["file_map"][rel_path] = info
    info_dict["byte_count"] += size
    return True


def read_folder_files(opts, folder_path):
    if opts.verbose >= 1:
        print 'Reading folder "%s" ...' % (folder_path, )
    res = create_info_dict()
    res["root_folder"] = folder_path

    for dirname, dirnames, filenames in os.walk(folder_path):
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
        print 'Parsing playlist "%s" ...' % (playlist_path, )
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
            fspec = canonical_path(fspec)
        add_file_info(opts, info, fspec)
    # TODO: faster sequential approach:
    # iparse = ET.iterparse(playlist_path, ["end", ])
    # for event, elem in iparse:
    #     if event == "end" and elem.tag == "media":
    #         print elem.attrib["src"]
    return


def read_source_files(opts):
    """Read source files (either complete folder or using given playlists)."""
    if len(opts.playlist_paths) == 0:
        return read_folder_files(opts, opts.source_folder)
    res = create_info_dict()
    res["root_folder"] = opts.source_folder
    for pl in opts.playlist_paths:
        ext = os.path.splitext(pl).lowercase()
        if ext == "wpl":
            read_playlist_wpl(opts, pl, res)
        else:
            raise NotImplementedError("Unsupported playlist extension: %r" % ext)
    return res


def sync_file_lists(opts, source_map, target_map):
    """Unify leading spaces and tabs and strip trailing whitespace.
    
    """
    # Pass 1: find and delete orphans
    # (before copying, so target space will be freed up)
#    target_folders = {}
    orphans = []
    for rel_path, target_info in target_map["file_map"].iteritems():
        src_info = source_map["file_map"].get(rel_path)
        if not src_info:
            orphans.append(target_info)

    if opts.delete_orphans:
        for o in orphans:
            fspec = o["fspec"]
            if opts.verbose >= 2:
                print 'DELETE: %s' % fspec
            delete_file(opts, fspec)

    # Pass 2: copy files
    identical_count = 0
    modified_count = 0
    new_count = 0
#    for rel_path, src_info in source_map["file_map"].iteritems():
    for rel_path in source_map["file_list"]:
        src_info = source_map["file_map"][rel_path]
        target_info = target_map["file_map"].get(rel_path)
        if target_info:
            if filecmp.cmp(src_info["fspec"], target_info["fspec"], shallow=True):
                # Identical
                identical_count += 1
                if opts.verbose >= 3:
                    print 'UNCHANGED: %s' % rel_path
            else:
                # Modified
                modified_count += 1
                if opts.verbose >= 2:
                    print 'UPDATE: %s' % rel_path
                # Copy with file dates
                shutil.copy2(src_info["fspec"], target_info["fspec"])
        else:
            # New
            new_count += 1
            if opts.verbose >= 2:
                print 'CREATE: %s' % rel_path
            target_fspec = os.path.join(opts.target_folder, rel_path)
            copy_file(opts, src_info["fspec"], target_fspec)

    if opts.verbose >= 1:
        # print('Compared %s files. Identical: %s, modified: %s, new: %s, orphans: %s.' 
        #       % (len(source_map["file_map"]), identical_count, modified_count, new_count, len(orphans)))
        print('Synchronized %s files. Created: %s, updated: %s, deleted: %s, unchanged: %s.' 
              % (len(source_map["file_map"]), new_count, modified_count, len(orphans), identical_count))

    # Pass 3: purge empty folders
    if opts.delete_orphans:
        purge_folders(opts, target_map)
#        for folder, has_data in target_map["folder_map"].iteritems():
#            print folder, has_data
    return


def run():
    # Create option parser for common and custom options
    parser = OptionParser(#prog="wplsync", # Otherwise 'wplsync-script.py' gets displayed on windows
                          version=__version__,
                          usage="usage: %prog [options] SOURCE_FOLDER TARGET_FOLDER [PLAYLIST [, PLAYLIST...]]",
                          description="Synchronize two media folders, optionally filtered by playlists.",
                          epilog="See also http://wplsync.googlecode.com")

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

    options.source_folder = canonical_path(args[0])
    options.target_folder = canonical_path(args[1])

    if not check_path_independent(options.source_folder, options.target_folder):
        parser.error("SOURCE_FOLDER and TARGET_FOLDER must not overlap")

    options.playlist_paths = []
    for pl in args[2:]:
        pl = canonical_path(pl)
        if not os.path.isfile(pl):
            parser.error("'%s' must be a playlist file" % pl)
        options.playlist_paths.append(pl)

    start_time = time.time()
    try:
        # Call processor
        source_info = read_source_files(options)
        target_info = read_folder_files(options, options.target_folder)

        if options.verbose >= 1:
            print "Source: %s files, %s valid in %s folders." % (source_info["process_count"],
                                                  len(source_info["file_map"]),
                                                  len(source_info["folder_map"])
                                                  )
            if options.verbose >= 2:
                ext_list = sorted(source_info["ext_map"].keys())
                print "    Extensions: %s" % ext_list
            print "Target: %s files, %s valid in %s folders." % (target_info["process_count"],
                                                  len(target_info["file_map"]),
                                                  len(target_info["folder_map"])
                                                  )
        sync_file_lists(options, source_info, target_info)
    except KeyboardInterrupt as e:
        print >>sys.stderr, "Interrupted!"

    if options.verbose >= 1:
        print "Elapsed: %.2f seconds." % (time.time() - start_time)
    if options.dry_run and options.verbose >= 1:
        print("\n*** Dry-run mode: no files have been modified!\n"
              "*** Use -x or --execute to process files.")


if __name__ == "__main__":
    run()
