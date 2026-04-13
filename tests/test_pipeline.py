from pathlib import Path

from graphmind.pipeline import run_pipeline


def test_pipeline_runs(tmp_path: Path) -> None:
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "app.py").write_text("def hello():\n    return 'ok'\n", encoding="utf-8")
    (sample / "README.md").write_text("# Title\n\n## Design\n", encoding="utf-8")

    out = run_pipeline(sample, incremental=False)

    assert out.detection.total_files == 2
    assert out.graph_nodes > 0
    assert out.graph_edges > 0
    assert (Path(out.out_dir) / "graph.json").exists()
    assert (Path(out.out_dir) / "graph.html").exists()
    assert (Path(out.out_dir) / "GRAPH_REPORT.md").exists()


def test_pipeline_includes_frontend_assets(tmp_path: Path) -> None:
    sample = tmp_path / "frontend-sample"
    sample.mkdir()
    (sample / "App.tsx").write_text(
        "import React from 'react'\n"
        "export function App() {\n"
        "  return <main className='app'>Hello</main>;\n"
        "}\n",
        encoding="utf-8",
    )
    (sample / "styles.css").write_text(".app { color: #222; }\n#root { margin: 0; }\n", encoding="utf-8")

    out = run_pipeline(sample, incremental=False)

    assert out.detection.total_files == 2
    assert any(path.endswith("App.tsx") for path in out.detection.files["code"])
    assert any(path.endswith("styles.css") for path in out.detection.files["code"])
    assert any(node.source_file.endswith("App.tsx") for node in out.extraction.nodes)
    assert any(node.source_file.endswith("styles.css") for node in out.extraction.nodes)
    assert any(node.kind in {"function", "component"} and node.label == "App" for node in out.extraction.nodes)
    assert any(node.kind == "import" and node.label == "react" for node in out.extraction.nodes)
    assert any(node.kind == "selector" and node.label in {".app", "#root"} for node in out.extraction.nodes)


def test_pipeline_extracts_typescript_symbols_and_jsx_refs(tmp_path: Path) -> None:
    sample = tmp_path / "ts-sample"
    sample.mkdir()
    (sample / "Widget.tsx").write_text(
        "import { useMemo } from 'react'\n"
        "export interface Props { title: string }\n"
        "export type Theme = 'light' | 'dark'\n"
        "export const Widget = ({ title }: Props) => {\n"
        "  const label = useMemo(() => title, [title])\n"
        "  return <Card>{label}</Card>\n"
        "}\n",
        encoding="utf-8",
    )

    out = run_pipeline(sample, incremental=False)

    assert out.detection.total_files == 1
    assert any(path.endswith("Widget.tsx") for path in out.detection.files["code"])
    assert any(node.kind == "import" and node.label == "react" for node in out.extraction.nodes)
    assert any(node.kind == "interface" and node.label == "Props" for node in out.extraction.nodes)
    assert any(node.kind == "type_alias" and node.label == "Theme" for node in out.extraction.nodes)
    assert any(node.kind == "component" and node.label == "Widget" for node in out.extraction.nodes)
    assert any(node.kind == "jsx_ref" and node.label == "Card" for node in out.extraction.nodes)


def test_pipeline_extracts_vue_and_svelte_components(tmp_path: Path) -> None:
    sample = tmp_path / "ui-sample"
    sample.mkdir()
    (sample / "Panel.vue").write_text(
        "<script setup>\n"
        "import Card from './Card.vue'\n"
        "const props = defineProps({ title: String, mode: String })\n"
        "const emit = defineEmits(['save'])\n"
        "const title = 'Panel'\n"
        "</script>\n"
        "<template>\n"
        "  <slot name='header' />\n"
        "  <Card />\n"
        "</template>\n",
        encoding="utf-8",
    )
    (sample / "Widget.svelte").write_text(
        "<script>\n"
        "import Modal from './Modal.svelte'\n"
        "export let name\n"
        "const selected = $cartStore\n"
        "</script>\n"
        "<slot />\n"
        "<Modal />\n",
        encoding="utf-8",
    )

    out = run_pipeline(sample, incremental=False)

    assert out.detection.total_files == 2
    assert any(path.endswith("Panel.vue") for path in out.detection.files["code"])
    assert any(path.endswith("Widget.svelte") for path in out.detection.files["code"])
    assert any(node.kind == "import" and node.label in {"./Card.vue", "./Modal.svelte"} for node in out.extraction.nodes)
    assert any(node.kind == "component" and node.label == "title" for node in out.extraction.nodes)
    assert any(node.kind == "prop" and node.label in {"title", "mode", "name"} for node in out.extraction.nodes)
    assert any(node.kind == "emit" and node.label == "save" for node in out.extraction.nodes)
    assert any(node.kind == "store" and node.label == "cartStore" for node in out.extraction.nodes)
    assert any(node.kind == "ui_ref" and node.label in {"Card", "Modal"} for node in out.extraction.nodes)
    assert any(node.kind == "slot" and node.label in {"header", "default"} for node in out.extraction.nodes)
