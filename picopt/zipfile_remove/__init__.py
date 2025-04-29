"""ZipFile with Remove method."""
# From https://github.com/python/cpython/pull/103033
# Not linted to compare against above PR
from zipfile import ZipFile, ZipInfo


class ZipFileWithRemove(ZipFile):
    """ZipFile with Remove method."""

    def remove(self, zinfo_or_arcname):
        """Remove a member from the archive."""
        if self.mode not in ('w', 'x', 'a'):
            raise ValueError("remove() requires mode 'w', 'x', or 'a'")
        if not self.fp:
            raise ValueError(
                "Attempt to write to ZIP archive that was already closed")
        if self._writing:
            raise ValueError(
                "Can't write to ZIP archive while an open writing handle exists"
            )

        # Make sure we have an existing info object
        if isinstance(zinfo_or_arcname, ZipInfo):
            zinfo = zinfo_or_arcname
            # make sure zinfo exists
            if zinfo not in self.filelist:
                raise KeyError(
                    'There is no item %r in the archive' % zinfo_or_arcname)
        else:
            # get the info object
            zinfo = self.getinfo(zinfo_or_arcname)

        return self._remove_members({zinfo})


    def _remove_members(self, members, *, remove_physical=True, chunk_size=2**20):
        """
        Remove members in a zip file.
        All members (as zinfo) should exist in the zip; otherwise the zip file
        will erroneously end in an inconsistent state.
        """
        fp = self.fp
        entry_offset = 0
        member_seen = False

        # get a sorted filelist by header offset, in case the dir order
        # doesn't match the actual entry order
        filelist = sorted(self.filelist, key=lambda x: x.header_offset)
        for i in range(len(filelist)):
            info = filelist[i]
            is_member = info in members

            if not (member_seen or is_member):
                continue

            # get the total size of the entry
            try:
                offset = filelist[i + 1].header_offset
            except IndexError:
                offset = self.start_dir
            entry_size = offset - info.header_offset

            if is_member:
                member_seen = True
                entry_offset += entry_size

                # update caches
                self.filelist.remove(info)
                try:
                    del self.NameToInfo[info.filename]
                except KeyError:
                    pass
                continue

            # update the header and move entry data to the new position
            if remove_physical:
                old_header_offset = info.header_offset
                info.header_offset -= entry_offset
                read_size = 0
                while read_size < entry_size:
                    fp.seek(old_header_offset + read_size)
                    data = fp.read(min(entry_size - read_size, chunk_size))
                    fp.seek(info.header_offset + read_size)
                    fp.write(data)
                    fp.flush()
                    read_size += len(data)

        # Avoid missing entry if entries have a duplicated name.
        # Reverse the order as NameToInfo normally stores the last added one.
        for info in reversed(self.filelist):
            self.NameToInfo.setdefault(info.filename, info)

        # update state
        if remove_physical:
            self.start_dir -= entry_offset
        self._didModify = True

        # seek to the start of the central dir
        fp.seek(self.start_dir)
