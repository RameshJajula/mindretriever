from __future__ import annotations

import re
from pathlib import Path

from graphmind.models import Edge, ExtractionResult, Node
from graphmind.security import redact_text

_UI_EXT = {".vue", ".svelte"}
_IMPORT_FROM_RE = re.compile(r"^\s*import\s+.+?from\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)
_REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", re.IGNORECASE)
_EXPORT_DEFAULT_RE = re.compile(r"^\s*export\s+default\b", re.IGNORECASE)
_FUNCTION_RE = re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)")
_CONST_RE = re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=")
_SVELTE_EXPORT_LET_RE = re.compile(r"^\s*export\s+let\s+([A-Za-z_][A-Za-z0-9_]*)")
_DEFINE_PROPS_OBJ_RE = re.compile(r"defineProps\(\s*\{([^}]*)\}\s*\)")
_DEFINE_PROPS_ARRAY_RE = re.compile(r"defineProps\(\s*\[([^\]]+)\]\s*\)")
_DEFINE_EMITS_ARRAY_RE = re.compile(r"defineEmits\(\s*\[([^\]]+)\]\s*\)")
_DEFINE_EMITS_OBJ_RE = re.compile(r"defineEmits\(\s*\{([^}]*)\}\s*\)")
_KEY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:")
_QUOTED_RE = re.compile(r"['\"]([^'\"]+)['\"]")
_STORE_REF_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
_COMPONENT_TAG_RE = re.compile(r"<([A-Z][A-Za-z0-9_]*)\b")
_SLOT_RE = re.compile(r"<slot(?:\s+name=['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"])?", re.IGNORECASE)


class VueSvelteSemanticExtractor:
    def __init__(self, *, redact_emails: bool = True, redact_keys: bool = True) -> None:
        self.redact_emails = redact_emails
        self.redact_keys = redact_keys

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in _UI_EXT

    def extract(self, path: Path) -> ExtractionResult:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = redact_text(raw, redact_emails=self.redact_emails, redact_keys=self.redact_keys)
        result = ExtractionResult()
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()

        file_id = f"ui::{path.stem}"
        result.nodes.append(Node(id=file_id, label=path.name, kind="ui_file", source_file=str(path)))
        seen_nodes.add(file_id)

        in_script = False
        in_template = path.suffix.lower() == ".svelte"

        for line_num, line in enumerate(text.splitlines(), start=1):
            lower_line = line.lower()
            if "<script" in lower_line:
                in_script = True
                if path.suffix.lower() == ".svelte":
                    in_template = False
                continue
            if "</script>" in lower_line:
                in_script = False
                if path.suffix.lower() == ".svelte":
                    in_template = True
                continue
            if path.suffix.lower() == ".vue":
                if "<template" in lower_line:
                    in_template = True
                    continue
                if "</template>" in lower_line:
                    in_template = False
                    continue

            if in_script:
                self._parse_script_line(result, seen_nodes, seen_edges, file_id, line, line_num, path)

            if in_template:
                self._parse_template_line(result, seen_nodes, seen_edges, file_id, line, line_num, path)

        return result

    def _parse_script_line(
        self,
        result: ExtractionResult,
        seen_nodes: set[str],
        seen_edges: set[tuple[str, str, str]],
        file_id: str,
        line: str,
        line_num: int,
        path: Path,
    ) -> None:
        import_match = _IMPORT_FROM_RE.match(line)
        if import_match:
            self._append_import(result, seen_nodes, seen_edges, file_id, import_match.group(1), line_num, path)

        for require_target in _REQUIRE_RE.findall(line):
            self._append_import(result, seen_nodes, seen_edges, file_id, require_target, line_num, path)

        if _EXPORT_DEFAULT_RE.match(line):
            self._append_symbol(
                result,
                seen_nodes,
                seen_edges,
                file_id,
                f"{path.stem}Default",
                "component",
                line_num,
                path,
                key_suffix="default",
            )

        for pattern, kind_name in ((_FUNCTION_RE, "function"), (_CONST_RE, "component"), (_SVELTE_EXPORT_LET_RE, "prop")):
            match = pattern.match(line)
            if match:
                self._append_symbol(result, seen_nodes, seen_edges, file_id, match.group(1), kind_name, line_num, path)

        for props_blob in _DEFINE_PROPS_OBJ_RE.findall(line):
            for prop_name in _KEY_RE.findall(props_blob):
                self._append_symbol(result, seen_nodes, seen_edges, file_id, prop_name, "prop", line_num, path)
        for props_blob in _DEFINE_PROPS_ARRAY_RE.findall(line):
            for prop_name in _QUOTED_RE.findall(props_blob):
                self._append_symbol(result, seen_nodes, seen_edges, file_id, prop_name, "prop", line_num, path)

        for emits_blob in _DEFINE_EMITS_ARRAY_RE.findall(line):
            for emit_name in _QUOTED_RE.findall(emits_blob):
                self._append_symbol(result, seen_nodes, seen_edges, file_id, emit_name, "emit", line_num, path)
        for emits_blob in _DEFINE_EMITS_OBJ_RE.findall(line):
            for emit_name in _KEY_RE.findall(emits_blob):
                self._append_symbol(result, seen_nodes, seen_edges, file_id, emit_name, "emit", line_num, path)

        for store_name in _STORE_REF_RE.findall(line):
            self._append_symbol(result, seen_nodes, seen_edges, file_id, store_name, "store", line_num, path)

    def _parse_template_line(
        self,
        result: ExtractionResult,
        seen_nodes: set[str],
        seen_edges: set[tuple[str, str, str]],
        file_id: str,
        line: str,
        line_num: int,
        path: Path,
    ) -> None:
        for component_tag in _COMPONENT_TAG_RE.findall(line):
            self._append_symbol(result, seen_nodes, seen_edges, file_id, component_tag, "ui_ref", line_num, path)

        for slot_name in _SLOT_RE.findall(line):
            normalized = slot_name if slot_name else "default"
            self._append_symbol(result, seen_nodes, seen_edges, file_id, normalized, "slot", line_num, path)

    def _append_symbol(
        self,
        result: ExtractionResult,
        seen_nodes: set[str],
        seen_edges: set[tuple[str, str, str]],
        file_id: str,
        name: str,
        kind: str,
        line_num: int,
        path: Path,
        *,
        key_suffix: str | None = None,
    ) -> None:
        safe_key = (key_suffix or name).lower()
        node_id = f"{kind}::{path.stem}::{safe_key}"
        if node_id not in seen_nodes:
            result.nodes.append(
                Node(
                    id=node_id,
                    label=name,
                    kind=kind,
                    source_file=str(path),
                    attributes={"line": line_num},
                )
            )
            seen_nodes.add(node_id)

        relation = "references" if kind in {"ui_ref", "slot"} else "contains"
        edge_key = (file_id, node_id, relation)
        if edge_key not in seen_edges:
            result.edges.append(
                Edge(
                    source=file_id,
                    target=node_id,
                    relation=relation,
                    confidence="EXTRACTED",
                    confidence_score=1.0,
                    source_file=str(path),
                )
            )
            seen_edges.add(edge_key)

    def _append_import(
        self,
        result: ExtractionResult,
        seen_nodes: set[str],
        seen_edges: set[tuple[str, str, str]],
        file_id: str,
        target: str,
        line_num: int,
        path: Path,
    ) -> None:
        import_id = f"import::{path.stem}::{target.lower()}"
        if import_id not in seen_nodes:
            result.nodes.append(
                Node(
                    id=import_id,
                    label=target,
                    kind="import",
                    source_file=str(path),
                    attributes={"line": line_num},
                )
            )
            seen_nodes.add(import_id)

        edge_key = (file_id, import_id, "imports")
        if edge_key not in seen_edges:
            result.edges.append(
                Edge(
                    source=file_id,
                    target=import_id,
                    relation="imports",
                    confidence="EXTRACTED",
                    confidence_score=1.0,
                    source_file=str(path),
                )
            )
            seen_edges.add(edge_key)
