"""The index: a local SQLite database over crawled repositories. Spec §6.

`schema.py` opens and creates it, `crawl.py` fills it from git, `queries.py` answers the
questions of spec §6. Nothing here runs a service or crawls anything it was not given.
"""

from cttp.index.schema import IndexingError, default_index_path, open_index

__all__ = ["IndexingError", "default_index_path", "open_index"]
