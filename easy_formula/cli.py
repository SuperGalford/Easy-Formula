from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import (
    add_visual_candidate,
    analyze_input,
    build_from_manifest,
    fill_text_fallback,
)
from .results import load_results, validate_results
from .pipeline import load_manifest


def _bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parts = [float(x.strip()) for x in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox 必须是 x0,y0,x1,y1") from exc
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox 必须包含 4 个数字")
    if parts[2] <= parts[0] or parts[3] <= parts[1]:
        raise argparse.ArgumentTypeError("bbox 的 x1/y1 必须大于 x0/y0")
    return tuple(parts)  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="easy-formula",
        description="识别 PDF 学术文献中的公式，转换为 LaTeX，并生成中文 DOCX。",
    )
    parser.add_argument("--version", action="version", version="Easy Formula 1.0.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="解析 PDF、检测公式候选并生成识别工作区。")
    p_analyze.add_argument("input", help="PDF 文件或 PDF 文件夹。")
    p_analyze.add_argument("--recursive", action="store_true", help="递归处理子文件夹。")
    p_analyze.add_argument("--output-dir", help="DOCX 输出目录；默认与原 PDF 同目录。")
    p_analyze.add_argument("--work-root", help="工作目录根路径。")
    p_analyze.add_argument("--no-inline", action="store_true", help="不检测行内公式。")

    p_build = sub.add_parser("build", help="根据已填写的识别结果生成 DOCX。")
    p_build.add_argument("manifest", help="analyze 生成的 manifest.json。")
    p_build.add_argument("--results", help="识别结果 JSON；默认读取 manifest 中的路径。")
    p_build.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的同名 DOCX。")
    p_build.add_argument("--allow-incomplete", action="store_true", help="忽略尚未确认的候选，仅输出已确认公式。")
    p_build.add_argument("--no-compile-check", action="store_true", help="跳过 pdflatex 编译检查。")

    p_text = sub.add_parser("text-auto", help="使用 PDF 文本层做低风险自动转换；准确率低于视觉 Agent。")
    p_text.add_argument("input", help="PDF 文件或 PDF 文件夹。")
    p_text.add_argument("--recursive", action="store_true")
    p_text.add_argument("--output-dir")
    p_text.add_argument("--work-root")
    p_text.add_argument("--no-inline", action="store_true")
    p_text.add_argument("--overwrite", action="store_true")
    p_text.add_argument("--no-compile-check", action="store_true")

    p_validate = sub.add_parser("validate", help="检查 recognition_results.json 是否完整。")
    p_validate.add_argument("manifest")
    p_validate.add_argument("--results")

    p_add = sub.add_parser("add-candidate", help="为扫描页补充视觉识别到的公式区域。")
    p_add.add_argument("manifest")
    p_add.add_argument("--page", type=int, required=True)
    p_add.add_argument("--bbox", type=_bbox, required=True, help="x0,y0,x1,y1")
    p_add.add_argument("--coords", choices=["pdf", "px"], default="pdf")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            manifests = analyze_input(
                args.input,
                recursive=args.recursive,
                output_dir=args.output_dir,
                work_root=args.work_root,
                include_inline=not args.no_inline,
            )
            print(f"共建立 {len(manifests)} 个识别工作区。")
            for m in manifests:
                data, candidates = load_manifest(m)
                print(f"- {Path(data['source_pdf']).name}")
                print(f"  候选公式：{len(candidates)}")
                print(f"  扫描页：{len(data.get('scan_pages', []))}")
                print(f"  清单：{m}")
                print(f"  识别结果：{data['results_path']}")
            return 0

        if args.command == "build":
            out = build_from_manifest(
                args.manifest,
                results_path=args.results,
                overwrite=args.overwrite,
                allow_incomplete=args.allow_incomplete,
                compile_latex=not args.no_compile_check,
            )
            print(f"DOCX 已生成：{out}")
            return 0

        if args.command == "text-auto":
            manifests = analyze_input(
                args.input,
                recursive=args.recursive,
                output_dir=args.output_dir,
                work_root=args.work_root,
                include_inline=not args.no_inline,
            )
            for m in manifests:
                fill_text_fallback(m)
                out = build_from_manifest(
                    m,
                    overwrite=args.overwrite,
                    compile_latex=not args.no_compile_check,
                )
                print(f"DOCX 已生成：{out}")
            return 0

        if args.command == "validate":
            manifest, candidates = load_manifest(args.manifest)
            results_path = args.results or manifest["results_path"]
            records = load_results(results_path)
            errors = validate_results(candidates, records)
            if errors:
                print("识别结果尚未完成：", file=sys.stderr)
                for e in errors:
                    print(f"- {e}", file=sys.stderr)
                return 1
            print("识别结果完整，可以生成 DOCX。")
            return 0

        if args.command == "add-candidate":
            cid = add_visual_candidate(args.manifest, args.page, args.bbox, coords=args.coords)
            print(f"已添加视觉候选：{cid}")
            return 0

    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
