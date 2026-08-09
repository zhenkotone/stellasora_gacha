from __future__ import annotations

import struct
from collections.abc import Iterable

from .lua53 import Lua53Reader, TAG_SHORT_STRING, TAG_TABLE
from .process import MemoryRegion, RemoteProcess


class LuaTableDiscovery:
    def __init__(self, process: RemoteProcess, lua: Lua53Reader):
        self.process = process
        self.lua = lua

    def _find_tstrings(self, text: str) -> list[int]:
        encoded = text.encode("utf-8")
        result: list[int] = []
        for data_address in self.process.scan(encoded):
            object_address = data_address - 24
            header = self.process.try_read(object_address, 24)
            if header is None or header[8] != 4 or header[11] != len(encoded):
                continue
            if self.process.try_read(data_address, len(encoded) + 1) != encoded + b"\0":
                continue
            result.append(object_address)
        return result

    def _find_key_nodes(self, string_addresses: Iterable[int]) -> list[int]:
        nodes: list[int] = []
        for string_address in string_addresses:
            pointer = struct.pack("<Q", string_address)
            for reference in self.process.scan(pointer):
                tag_raw = self.process.try_read(reference + 8, 4)
                if tag_raw is None or struct.unpack("<i", tag_raw)[0] != TAG_SHORT_STRING:
                    continue
                node_address = reference - 16
                if node_address % 8 == 0:
                    nodes.append(node_address)
        return nodes

    @staticmethod
    def _nearby_regions(regions: list[MemoryRegion], address: int, radius: int) -> list[MemoryRegion]:
        low, high = max(0, address - radius), address + radius
        return [region for region in regions if region.end > low and region.base < high]

    def _tables_containing_node(self, node_address: int) -> list[int]:
        candidates: list[int] = []
        # Lua tables and their node arrays normally live in the same allocator arena.
        # A generous local window avoids another full-process structural scan.
        regions = self._nearby_regions(self.process.regions(), node_address, 64 * 1024 * 1024)
        for region in regions:
            data = self.process.try_read(region.base, region.size)
            if data is None:
                continue
            start = (-region.base) % 8
            for offset in range(start, max(start, len(data) - 48), 8):
                if data[offset + 8] != 5:
                    continue
                lsize_node = data[offset + 11]
                if lsize_node > 20:
                    continue
                node_ptr = struct.unpack_from("<Q", data, offset + 24)[0]
                node_count = 1 << lsize_node
                delta = node_address - node_ptr
                if 0 <= delta < node_count * 32 and delta % 32 == 0:
                    candidates.append(region.base + offset)
        return candidates

    def find_instance_table(self, field: str, companion_fields: set[str]) -> int:
        strings = self._find_tstrings(field)
        if not strings:
            raise LookupError(f"未找到 Lua 字段字符串 {field}")
        nodes = self._find_key_nodes(strings)
        checked: set[int] = set()
        for node in nodes:
            for table in self._tables_containing_node(node):
                if table in checked:
                    continue
                checked.add(table)
                try:
                    field_value = self.lua.get_table_field_tvalue(table, field)
                    if field_value is None or field_value.tag != TAG_TABLE:
                        continue
                    matches = sum(
                        self.lua.get_table_field_tvalue(table, name) is not None
                        for name in companion_fields
                    )
                    if matches >= min(2, len(companion_fields)):
                        return table
                except (OSError, ValueError):
                    continue
        raise LookupError(f"找到字段 {field}，但无法确认所属的 Lua 实例表")

    def read_target_field(self, field: str, companion_fields: set[str]):
        instance = self.find_instance_table(field, companion_fields)
        value = self.lua.get_table_field_tvalue(instance, field)
        if value is None or value.tag != TAG_TABLE:
            raise LookupError(f"Lua 字段 {field} 不是表")
        return self.lua.decode_tvalue(value)

