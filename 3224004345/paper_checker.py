"""论文查重的核心计算和命令行接口。"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path
from typing import Sequence


def normalize_text(text: str) -> str:
    """规范化文本并移除不参与查重的空白、标点和符号。"""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace()
        and unicodedata.category(character)[0] not in {"P", "S", "Z"}
    )


def _ngrams(text: str, size: int) -> list[str]:
    """按指定长度生成连续字符片段。"""
    return [text[index : index + size] for index in range(len(text) - size + 1)]


def _dice_similarity(left: list[str], right: list[str]) -> float:
    """用朴素匹配计算两个多重集的 Sørensen-Dice 系数。"""
    if not left and not right:
        return 1.0

    unmatched = right.copy()
    overlap = 0
    for item in left:
        if item in unmatched:
            unmatched.remove(item)
            overlap += 1
    return 2.0 * overlap / (len(left) + len(right))


def calculate_similarity(original: str, suspect: str) -> float:
    """计算两个文本在 0.0 到 1.0 范围内的重复率。"""
    normalized_original = normalize_text(original)
    normalized_suspect = normalize_text(suspect)

    if not normalized_original and not normalized_suspect:
        return 1.0
    if not normalized_original or not normalized_suspect:
        return 0.0

    unigram_score = _dice_similarity(
        _ngrams(normalized_original, 1),
        _ngrams(normalized_suspect, 1),
    )
    if len(normalized_original) < 2 or len(normalized_suspect) < 2:
        return unigram_score

    bigram_score = _dice_similarity(
        _ngrams(normalized_original, 2),
        _ngrams(normalized_suspect, 2),
    )
    score = 0.2 * unigram_score + 0.8 * bigram_score
    return min(1.0, max(0.0, score))


def _read_text(path_value: str | Path) -> str:
    path = Path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"输入文件不存在或不是普通文件：{path}")

    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"无法以 UTF-8 或 GB18030 解码文件：{path}")


def run(
    original_path: str | Path,
    suspect_path: str | Path,
    output_path: str | Path,
) -> None:
    """读取两篇论文，计算重复率并写入指定答案文件。"""
    original = _read_text(original_path)
    suspect = _read_text(suspect_path)
    score = calculate_similarity(original, suspect)
    Path(output_path).write_text(f"{score:.2f}\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """执行命令行程序，并返回稳定的进程退出码。"""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 3:
        print("用法：python main.py [原文文件] [抄袭版论文文件] [答案文件]", file=sys.stderr)
        return 2

    try:
        run(arguments[0], arguments[1], arguments[2])
    except (OSError, UnicodeError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0

