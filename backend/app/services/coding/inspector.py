"""Safe static code inspector, AST parser, and workspace path validator."""

import ast
import os
from pathlib import Path
from typing import List, Optional
from app.services.coding.schemas import (
    CodeFileInfo,
    CodeSymbolInfo,
    InspectCodeResponse,
)


class CodeInspector:
    """Safe, sandboxed static code analyzer using Python's native AST."""

    IGNORED_DIRS = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        ".gemini",
        "dist",
        "build",
    }

    @staticmethod
    def validate_safe_path(base_dir: str, target_path: str) -> Path:
        """Enforce path resolution strictly within workspace boundaries (path-traversal defense)."""
        base = Path(base_dir).resolve()
        target = Path(target_path)
        if not target.is_absolute():
            target = (base / target).resolve()
        else:
            target = target.resolve()

        try:
            target.relative_to(base)
        except ValueError:
            raise ValueError(f"Path traversal blocked: '{target}' is outside workspace '{base}'")

        return target

    @classmethod
    def inspect_file(cls, file_path: Path, include_symbols: bool = True) -> CodeFileInfo:
        """Inspect a single code file for size, lines, syntax validity, and AST symbols."""
        if not file_path.exists() or not file_path.is_file():
            return CodeFileInfo(
                path=str(file_path),
                size_bytes=0,
                line_count=0,
                syntax_valid=False,
                syntax_error="File does not exist or is not a regular file.",
            )

        content = ""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as err:
            return CodeFileInfo(
                path=str(file_path),
                size_bytes=0,
                line_count=0,
                syntax_valid=False,
                syntax_error=f"Read error: {err}",
            )

        size_bytes = len(content.encode("utf-8"))
        lines = content.splitlines()
        line_count = len(lines)

        symbols: List[CodeSymbolInfo] = []
        syntax_valid = True
        syntax_error = None

        if file_path.suffix.lower() == ".py":
            try:
                tree = ast.parse(content, filename=str(file_path))
                if include_symbols:
                    symbols = cls.extract_ast_symbols(tree)
            except SyntaxError as err:
                syntax_valid = False
                syntax_error = f"Syntax error at line {err.lineno}: {err.msg}"
            except Exception as err:
                syntax_valid = False
                syntax_error = f"AST parse error: {err}"

        return CodeFileInfo(
            path=str(file_path),
            size_bytes=size_bytes,
            line_count=line_count,
            syntax_valid=syntax_valid,
            syntax_error=syntax_error,
            symbols=symbols,
        )

    @classmethod
    def extract_ast_symbols(cls, tree: ast.AST) -> List[CodeSymbolInfo]:
        """Extract top-level and class-level classes and functions."""
        symbols: List[CodeSymbolInfo] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                symbols.append(
                    CodeSymbolInfo(
                        name=node.name,
                        kind="class",
                        line_number=node.lineno,
                        docstring=doc,
                    )
                )
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        doc_fn = ast.get_docstring(item)
                        arg_names = [a.arg for a in item.args.args]
                        symbols.append(
                            CodeSymbolInfo(
                                name=f"{node.name}.{item.name}",
                                kind="async_function" if isinstance(item, ast.AsyncFunctionDef) else "function",
                                line_number=item.lineno,
                                docstring=doc_fn,
                                args=arg_names,
                            )
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                arg_names = [a.arg for a in node.args.args]
                symbols.append(
                    CodeSymbolInfo(
                        name=node.name,
                        kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                        line_number=node.lineno,
                        docstring=doc,
                        args=arg_names,
                    )
                )
        return symbols

    @classmethod
    def inspect_workspace(
        cls,
        workspace_path: str,
        relative_file_path: Optional[str] = None,
        max_depth: int = 3,
        include_symbols: bool = False,
    ) -> InspectCodeResponse:
        """Scan workspace files or specific file with depth and exclusion guards."""
        root = Path(workspace_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Workspace directory not found: '{root}'")

        if relative_file_path:
            safe_target = cls.validate_safe_path(str(root), relative_file_path)
            file_info = cls.inspect_file(safe_target, include_symbols=include_symbols)
            return InspectCodeResponse(
                workspace_path=str(root),
                total_files=1,
                files=[file_info],
                summary=f"Inspected single file '{relative_file_path}' ({file_info.line_count} lines).",
            )

        collected: List[CodeFileInfo] = []
        root_depth = len(root.parts)

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored directories
            dirnames[:] = [d for d in dirnames if d not in cls.IGNORED_DIRS and not d.startswith(".")]

            current_depth = len(Path(dirpath).parts) - root_depth
            if current_depth >= max_depth:
                dirnames.clear()
                continue

            for fname in filenames:
                if fname.startswith("."):
                    continue
                ext = Path(fname).suffix.lower()
                if ext in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".toml", ".yaml", ".yml"}:
                    fpath = Path(dirpath) / fname
                    info = cls.inspect_file(fpath, include_symbols=include_symbols)
                    collected.append(info)

        summary = f"Scanned {len(collected)} files in '{root.name}' up to depth {max_depth}."
        return InspectCodeResponse(
            workspace_path=str(root),
            total_files=len(collected),
            files=collected,
            summary=summary,
        )
