import xml.etree.ElementTree as ET
from .base import BaseConverter


class DrawioConverter(BaseConverter):

    COLOR_CHANGE = "#0050ef"
    COLOR_CREATE = "#00be64"
    COLOR_OWNED = "#FFF2CC"

    def convert(self, path: str) -> str:
        tree = ET.parse(path)
        root = tree.getroot()

        cells = root.findall(".//mxCell")

        # maps id -> cell metadata
        cell_map = {}

        systems = {}
        relations = []

        # ---------------------------------------------------
        # PASS 1 — collect metadata about all cells
        # ---------------------------------------------------
        for cell in cells:
            cid = cell.get("id")
            style = (cell.get("style") or "").lower()
            parent = cell.get("parent")

            is_system = "swimlane" in style or "container=1" in style
            is_capability = ("container=0" in style) and cell.get("vertex") == "1"

            cell_map[cid] = {
                "id": cid,
                "name": self._clean(cell.get("value") or ""),
                "style": style,
                "parent": parent,
                "raw": cell,
                "is_system": is_system,
                "is_capability": is_capability,
                "capabilities": [],
            }

            if is_system:
                systems[cid] = cell_map[cid]

        # ---------------------------------------------------
        # PASS 2 — assign capabilities to systems
        # ---------------------------------------------------
        for cell in cell_map.values():
            if not cell["is_capability"]:
                continue

            parent_id = cell["parent"]
            # capability can belong to nested system too
            sys_id = self._resolve_system_id(parent_id, cell_map)
            if sys_id and sys_id in systems:
                systems[sys_id]["capabilities"].append(cell)

        # ---------------------------------------------------
        # PASS 3 — parse edges / relations
        # ---------------------------------------------------
        for cell in cells:
            if cell.get("edge") != "1":
                continue

            rid = cell.get("id")
            style = (cell.get("style") or "").lower()
            text = self._clean(cell.get("value") or "")

            src_raw = cell.get("source")
            tgt_raw = cell.get("target")

            src = self._resolve_system_id(src_raw, cell_map)
            tgt = self._resolve_system_id(tgt_raw, cell_map)

            if not src and not tgt:
                continue

            rtype = ""
            if f"strokecolor={self.COLOR_CHANGE}" in style:
                rtype = "изменение"
            elif f"strokecolor={self.COLOR_CREATE}" in style:
                rtype = "создание"

            relations.append({
                "from": systems[src]["name"] if src else "",
                "to": systems[tgt]["name"] if tgt else "",
                "text": text,
                "type": rtype,
            })

        # ---------------------------------------------------
        # BUILD MARKDOWN
        # ---------------------------------------------------
        md = []
        md.append("# Системы\n")
        md.append(self._md_systems(systems))
        md.append("\n\n# Связи\n")
        md.append(self._md_relations(relations))

        return "\n".join(md)

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _resolve_system_id(self, cid, cmap):
        """Поднимаемся по parent пока не встретим систему."""
        if cid not in cmap:
            return None

        current = cmap[cid]
        visited = set()

        while current:
            if current["is_system"]:
                return current["id"]

            parent_id = current.get("parent")
            if not parent_id or parent_id in visited:
                return None

            visited.add(parent_id)
            current = cmap.get(parent_id)

        return None

    def _md_systems(self, systems: dict):
        md = ["| система | способности | тип |", "|---|---|---|"]

        # sort by system name
        sorted_systems = sorted(systems.values(), key=lambda s: s["name"].lower())

        for sys in sorted_systems:
            caps_text = ", ".join(c["name"] for c in sys["capabilities"])
            stype = self._detect_type(sys["style"])
            md.append(f"| {sys['name']} | {caps_text} | {stype} |")

        return "\n".join(md)

    def _md_relations(self, relations: list):
        md = ["| from | to | текст | тип |", "|---|---|---|---|"]

        for r in relations:
            md.append(f"| {r['from']} | {r['to']} | {r['text']} | {r['type']} |")

        return "\n".join(md)

    def _detect_type(self, style):
        style = style.lower()
        if f"strokecolor={self.COLOR_CHANGE}" in style:
            return "изменение"
        if f"strokecolor={self.COLOR_CREATE}" in style:
            return "создание"
        return "использование"

    def _clean(self, text: str):
        return (text
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("<br>", " ")
                .replace("\n", " ")
                .strip())
