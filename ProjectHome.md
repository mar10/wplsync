### Status ###
**This project has beta status: use at your own risk!**

Please submit bugs as you find them.




### Summary ###
Python console script to synchronize media folders, using playlists as filter.

  * Read one or more playlists (`*`.WPL) and copy referenced files to target folder.
  * If no playlist is specified, the complete source media folder will be synchronized.
  * Source directory structure is maintained in the target folder.
  * Duplicate, or otherwise invalid playlist entries are ignored.
  * `-d` option removes unmatched files and empty folders from target.

### Usage ###
**Preconditions:** [Python](http://www.python.org/download/) is required,
[EasyInstall](http://pypi.python.org/pypi/setuptools#using-setuptools-and-easyinstall)
recommended.

Install like this:

<pre>
$sudo easy_install -U wplsync<br>
</pre>

or on Windows:
<pre>
>easy_install -U wplsync<br>
</pre>

**Syntax**:
```sh

C:\>wplsync -h
Usage: wplsync [options] SOURCE_FOLDER TARGET_FOLDER [PLAYLIST [, PLAYLIST...]]

Synchronize two media folders, optionally filtered by playlists.

Options:
--version      show program's version number and exit
-h, --help     show this help message and exit
-x, --execute  turn off the dry-run mode (which is ON by default), that
would just print status messages but does not change anything
-q, --quiet    don't print status messages to stdout (verbosity 0)
-v, --verbose  increment verbosity to 2 (use -vv for 3, ...)
-d, --delete   delete target files that don't exist in PLAYLIST

See also http://wplsync.googlecode.com

C:\>
```