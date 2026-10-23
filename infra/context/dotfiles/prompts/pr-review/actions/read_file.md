Use `read_file` to read a file at the pull request's head revision before changing it, and return that file's
complete new content. It reads repository-relative paths only and refuses files that are too large or hold
credential material; leave a refused file unchanged.
