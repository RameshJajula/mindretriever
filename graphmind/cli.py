from __future__ import annotations

import argparse

from graphmind.pipeline import run_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mindretriever", description="MindRetriever CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run full graph pipeline")
    run_cmd.add_argument("path", nargs="?", default=".", help="Target root directory")
    run_cmd.add_argument("--full", action="store_true", help="Disable incremental mode")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        output = run_pipeline(args.path, incremental=not args.full)
        print(f"GraphMind complete. Files={output.detection.total_files} Nodes={output.graph_nodes} Edges={output.graph_edges} Communities={output.communities}")
        print(f"Artifacts: {output.out_dir}")
