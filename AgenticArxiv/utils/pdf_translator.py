# AgenticArxiv/utils/pdf_translator.py
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple

from utils.logger import log


@dataclass(frozen=True)
class Pdf2ZhResult:
    mono_path: str
    dual_path: Optional[str]
    stdout_path: Optional[str] = None


def _guess_outputs(out_dir: str, stem: str) -> Tuple[str, str]:
    """
    不同版本可能是 -mono / -zh 命名，这里做兼容：
    mono_candidates: stem-mono.pdf or stem-zh.pdf
    dual: stem-dual.pdf
    """
    mono1 = os.path.join(out_dir, f"{stem}-mono.pdf")
    mono2 = os.path.join(out_dir, f"{stem}-zh.pdf")
    dual = os.path.join(out_dir, f"{stem}-dual.pdf")
    mono = mono1 if os.path.exists(mono1) else mono2
    return mono, dual


def run_pdf2zh_translate(
    pdf2zh_bin: str,
    input_pdf: str,
    out_dir: str,
    service: str = "bing",
    threads: int = 4,
    keep_dual: bool = False,
    log_path: Optional[str] = None,
) -> Pdf2ZhResult:
    """
    调用 pdf2zh 翻译全文：
      pdf2zh input.pdf -s bing -o out_dir -t 4
    默认只保留 mono，dual 会被删除（除非 keep_dual=True）。
    """
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"input pdf not found: {input_pdf}")

    bin_path = shutil.which(pdf2zh_bin) or pdf2zh_bin
    if shutil.which(bin_path) is None and not os.path.exists(bin_path):
        raise RuntimeError(
            f"未找到 pdf2zh 可执行文件：{pdf2zh_bin}。"
            f"请先安装：pip install pdf2zh，或设置环境变量 PDF2ZH_BIN 指向可执行文件。"
        )

    os.makedirs(out_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(input_pdf))[0]

    cmd = [
        bin_path,
        input_pdf,
        "-s",
        service,
        "-o",
        out_dir,
        "-t",
        str(int(threads)),
    ]

    log.info(f"Run pdf2zh: {' '.join(cmd)}")

    stdout_file = None
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        stdout_file = open(log_path, "w", encoding="utf-8")
    try:
        subprocess.run(
            cmd,
            stdout=stdout_file or subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
        )
    finally:
        if stdout_file:
            stdout_file.close()

    mono, dual = _guess_outputs(out_dir, stem)

    if not os.path.exists(mono):
        raise RuntimeError(
            f"pdf2zh 执行成功但未找到 mono 输出文件，期望位置之一："
            f"{os.path.join(out_dir, stem + '-mono.pdf')} 或 {os.path.join(out_dir, stem + '-zh.pdf')}"
        )

    dual_exists = os.path.exists(dual)
    if dual_exists and not keep_dual:
        try:
            os.remove(dual)
        except Exception as e:
            log.warning(f"删除 dual 失败（不影响返回 mono）：{dual}, err={e}")

    return Pdf2ZhResult(
        mono_path=mono,
        dual_path=dual if (dual_exists and keep_dual) else None,
        stdout_path=log_path,
    )
