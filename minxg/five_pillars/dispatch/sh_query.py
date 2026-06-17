"""
text_grep, archive_create, archive_extract, get_system_info,
get_process_list, get_network_info
"""
from __future__ import annotations
from typing import Dict
from minxg.base import BaseWorker, tool
from minxg.five_pillars.io.fs_io import FsIoWorker
from minxg.five_pillars.io.fs_search import FsSearchWorker
from minxg.five_pillars.dispatch.system import SystemWorker


class ShQueryWorker(BaseWorker):
    worker_id = "sh_query"
    version = "0"

    def __init__(self):
        super().__init__()
        self._fs = FsIoWorker()
        self._fs_search = FsSearchWorker()
        self._sys = SystemWorker()

    @tool(description="Read file", category="file")
    async def file_read(self, path: str) -> Dict:
        r = await self._fs.read_file(path=path)
        return r if "error" in r else {"content": r.get("content", "")}

    @tool(description="Write file", category="file")
    async def file_write(self, path: str, content: str) -> Dict:
        return await self._fs.write_file(path=path, content=content)

    @tool(description="List directory", category="file")
    async def file_list(self, path: str = ".") -> Dict:
        return await self._fs.list_directory(path=path)

    @tool(description="Search by filename", category="file")
    async def file_search(self, pattern: str, path: str = ".") -> Dict:
        return await self._fs_search.glob_search(pattern=pattern, path=path)

    @tool(description="Content search (grep)", category="text")
    async def text_grep(self, pattern: str, path: str) -> Dict:
        return await self._fs_search.grep_file(pattern=pattern, path=path)

    @tool(description="Create archive", category="archive")
    async def archive_create(self, source: str, output: str, format: str = "zip") -> Dict:
        return await self._fs_search.compress(source=source, output=output, format=format)

    @tool(description="Extract archive", category="archive")
    async def archive_extract(self, archive: str, output_dir: str = ".") -> Dict:
        return await self._fs_search.decompress(archive=archive, output_dir=output_dir)

    @tool(description="System info", category="info")
    async def get_system_info(self) -> Dict:
        return await self._sys.system_info(detailed=True)

    @tool(description="Process list", category="info")
    async def get_process_list(self, filter: str = "") -> Dict:
        return await self._sys.process_list(filter_name=filter)

    @tool(description="Network info", category="info")
    async def get_network_info(self) -> Dict:
        return await self._sys.network_info()
