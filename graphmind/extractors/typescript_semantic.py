from __future__ import annotations

import re
from pathlib import Path

from graphmind.models import Edge, ExtractionResult, Node
from graphmind.security import redact_text

_TS_EXT = {".ts", ".tsx", ".js", ".jsx"}
_IMPORT_FROM_RE = re.compile(r"^\s*import\s+.+?from\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)
_REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", re.IGNORECASE)
_EXPORT_DEFAULT_FUNCTION_RE = re.compile(r"^\s*export\s+default\s+function\s+([A-Za-z_][A-Za-z0-9_]*)")
_EXPORT_FUNCTION_RE = re.compile(r"^\s*export\s+function\s+([A-Za-z_][A-Za-z0-9_]*)")
_FUNCTION_RE = re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)")
_EXPORT_CLASS_RE = re.compile(r"^\s*export\s+class\s+([A-Za-z_][A-Za-z0-9_]*)")
_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)")
_INTERFACE_RE = re.compile(r"^\s*export\s+interface\s+([A-Za-z_][A-Za-z0-9_]*)|^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)")
_TYPE_ALIAS_RE = re.compile(r"^\s*export\s+type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=|^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=")
_CONST_FN_RE = re.compile(
    r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(|async\s*\()",
    re.IGNORECASE,
)
_JSX_TAG_RE = re.compile(r"<([A-Z][A-Za-z0-9_]*)\b")


class TypeScriptSemanticExtractor:
    def __init__(self, *, redact_emails: bool = True, redact_keys: bool = True) -> None:
        self.redact_emails = redact_emails
        self.redact_keys = redact_keys

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in _TS_EXT

    def extract(self, path: Path) -> ExtractionResult:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = redact_text(raw, redact_emails=self.redact_emails, redact_keys=self.redact_keys)
        result = ExtractionResult()
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()

        file_id = f"code::{path.stem}"
        result.nodes.append(Node(id=file_id, label=path.name, kind="code_file", source_file=str(path)))
        seen_nodes.add(file_id)

        for line_num, line in enumerate(text.splitlines(), start=1):
            import_match = _IMPORT_FROM_RE.match(line)
            if import_match:
                self._append_import(result, seen_nodes, seen_edges, file_id, import_match.group(1), line_num, path)

            for require_target in _REQUIRE_RE.findall(line):
                self._append_import(result, seen_nodes, seen_edges, file_id, require_target, line_num, path)

            symbol_name = None
            symbol_kind = None

            for pattern, kind_name in (
                (_EXPORT_DEFAULT_FUNCTION_RE, "function"),
                (_EXPORT_FUNCTION_RE, "function"),
                (_FUNCTION_RE, "function"),
                (_EXPORT_CLASS_RE, "class"),
                (_CLASS_RE, "class"),
                (_CONST_FN_RE, "component"),
            ):
                match = pattern.match(line)
                if match:
                    symbol_name = match.group(1)
                    symbol_kind = kind_name
                    break

            if symbol_name and symbol_kind:
                self._append_symbol(
                    result,
                    seen_nodes,
                    seen_edges,
                    file_id,
                    symbol_name,
                    symbol_kind,
                    line_num,
                    path,
                )

            interface_match = _INTERFACE_RE.match(line)
            if interface_match:
                interface_name = interface_match.group(1) or interface_match.group(2)
                if interface_name:
                    self._append_symbol(
                        result,
                        seen_nodes,
                        seen_edges,
                        file_id,
                        interface_name,
                        "interface",
                        line_num,
                        path,
                    )

            type_alias_match = _TYPE_ALIAS_RE.match(line)
            if type_alias_match:
                alias_name = type_alias_match.group(1) or type_alias_match.group(2)
                if alias_name:
                    self._append_symbol(
                        result,
                        seen_nodes,
                        seen_edges,
                        file_id,
                        alias_name,
                        "type_alias",
                        line_num,
                        path,
                    )

            for jsx_tag in _JSX_TAG_RE.findall(line):
                ref_id = f"jsx_ref::{path.stem}::{jsx_tag.lower()}"
                if ref_id not in seen_nodes:
                    result.nodes.append(
                        Node(
                            id=ref_id,
                            label=jsx_tag,
                            kind="jsx_ref",
                            source_file=str(path),
                            attributes={"line": line_num},
                        )
                    )
                    seen_nodes.add(ref_id)

                edge_key = (file_id, ref_id, "references")
                if edge_key not in seen_edges:
                    result.edges.append(
                        Edge(
                            source=file_id,
                            target=ref_id,
                            relation="references",
                            confidence="EXTRACTED",
                            confidence_score=1.0,
                            source_file=str(path),
                        )
                    )
                    seen_edges.add(edge_key)

        return result

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

    def _append_symbol(
        self,
        result: ExtractionResult,
        seen_nodes: set[str],
        seen_edges: set[tuple[str, str, str]],
        file_id: str,
        symbol_name: str,
        symbol_kind: str,
        line_num: int,
        path: Path,
    ) -> None:
        symbol_id = f"{symbol_kind}::{path.stem}::{symbol_name.lower()}"
        if symbol_id not in seen_nodes:
            result.nodes.append(
                Node(
                    id=symbol_id,
                    label=symbol_name,
                    kind=symbol_kind,
                    source_file=str(path),
                    attributes={"line": line_num},
                )
            )
            seen_nodes.add(symbol_id)

        edge_key = (file_id, symbol_id, "contains")
        if edge_key not in seen_edges:
            result.edges.append(
                Edge(
                    source=file_id,
                    target=symbol_id,
                    relation="contains",
                    confidence="EXTRACTED",
                    confidence_score=1.0,
                    source_file=str(path),
                )
            )
            seen_edges.add(edge_key)
