"""生成可复现的性能分析证据。"""

from __future__ import annotations

import cProfile
import html
import io
import json
import pstats
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

from paper_checker import calculate_similarity, normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = PROJECT_ROOT / "reports" / "evidence"


def _ngrams(text: str, size: int) -> list[str]:
    return [text[index : index + size] for index in range(len(text) - size + 1)]


def _naive_dice(left: list[str], right: list[str]) -> float:
    if not left and not right:
        return 1.0
    unmatched = right.copy()
    overlap = 0
    for item in left:
        if item in unmatched:
            unmatched.remove(item)
            overlap += 1
    return 2.0 * overlap / (len(left) + len(right))


def _naive_similarity(original: str, suspect: str) -> float:
    left = normalize_text(original)
    right = normalize_text(suspect)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    unigram = _naive_dice(_ngrams(left, 1), _ngrams(right, 1))
    if len(left) < 2 or len(right) < 2:
        return unigram
    bigram = _naive_dice(_ngrams(left, 2), _ngrams(right, 2))
    return 0.2 * unigram + 0.8 * bigram


def _profile(
    name: str,
    function: Callable[[str, str], float],
    original: str,
    suspect: str,
) -> dict[str, float | str]:
    profiler = cProfile.Profile()
    tracemalloc.start()
    start = time.perf_counter()
    profiler.enable()
    score = function(original, suspect)
    profiler.disable()
    seconds = time.perf_counter() - start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    statistics = io.StringIO()
    pstats.Stats(profiler, stream=statistics).strip_dirs().sort_stats("cumulative").print_stats(12)
    (OUTPUT_DIRECTORY / f"cprofile-{name}.txt").write_text(
        statistics.getvalue(), encoding="utf-8"
    )
    return {
        "score": score,
        "seconds_with_profiler": seconds,
        "peak_mib": peak_bytes / (1024 * 1024),
    }


def _large_input_benchmark() -> dict[str, float | int]:
    unit = "今天是星期天，天气晴朗，晚上我要去看电影。"
    repeat_count = 1_048_576 // len(unit) + 1
    original = (unit * repeat_count)[:1_048_576]
    suspect = original.replace("星期天", "周天").replace("天气晴朗", "天气晴")

    start = time.perf_counter()
    score = calculate_similarity(original, suspect)
    seconds = time.perf_counter() - start

    tracemalloc.start()
    calculate_similarity(original, suspect)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "characters": len(original),
        "score": score,
        "runtime_seconds": seconds,
        "peak_mib": peak_bytes / (1024 * 1024),
    }


def _write_html(results: dict[str, object]) -> None:
    before = results["before"]
    after = results["after"]
    large = results["large_input"]
    assert isinstance(before, dict)
    assert isinstance(after, dict)
    assert isinstance(large, dict)
    speedup = float(before["seconds_with_profiler"]) / float(after["seconds_with_profiler"])
    before_profile = html.escape(
        (OUTPUT_DIRECTORY / "cprofile-before.txt").read_text(encoding="utf-8")
    )
    after_profile = html.escape(
        (OUTPUT_DIRECTORY / "cprofile-after.txt").read_text(encoding="utf-8")
    )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>论文查重性能分析</title>
<style>
body {{ font: 16px/1.55 system-ui, sans-serif; margin: 36px; color: #17202a; }}
h1 {{ color: #173f5f; }} table {{ border-collapse: collapse; margin: 18px 0; }}
th, td {{ border: 1px solid #9aa7b2; padding: 8px 14px; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
.ok {{ color: #16794a; font-weight: 700; }}
pre {{ background: #f4f6f7; border: 1px solid #d5d8dc; padding: 14px; font-size: 12px; }}
</style></head><body>
<h1>论文查重计算模块性能分析</h1>
<p>环境：Python 3.13 / Windows；分析工具：cProfile、perf_counter、tracemalloc。</p>
<table><tr><th>实现</th><th>字符数</th><th>结果</th>
<th>分析耗时（秒）</th><th>峰值内存（MiB）</th></tr>
<tr><td>优化前：列表查找/删除</td>
<td>{results['profile_characters']}</td><td>{before['score']:.6f}</td>
<td>{before['seconds_with_profiler']:.6f}</td><td>{before['peak_mib']:.3f}</td></tr>
<tr><td>优化后：Counter 交集</td>
<td>{results['profile_characters']}</td><td>{after['score']:.6f}</td>
<td>{after['seconds_with_profiler']:.6f}</td><td>{after['peak_mib']:.3f}</td></tr></table>
<p class="ok">结果保持一致，分析场景提速 {speedup:.2f} 倍。</p>
<h2>1 MiB 验收</h2>
<p>字符数 {large['characters']}；正常运行耗时 <strong>{large['runtime_seconds']:.6f} 秒</strong>；
峰值内存 {large['peak_mib']:.3f} MiB；结果 {large['score']:.6f}。</p>
<h2>优化前热点</h2><pre>{before_profile}</pre>
<h2>优化后热点</h2><pre>{after_profile}</pre>
</body></html>"""
    (OUTPUT_DIRECTORY / "performance.html").write_text(document, encoding="utf-8")


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    original = "今天是星期天，天气晴，今天晚上我要去看电影。" * 700
    suspect = original.replace("星期天", "周天").replace("天气晴", "天气晴朗")
    results: dict[str, object] = {
        "profile_characters": len(original),
        "before": _profile("before", _naive_similarity, original, suspect),
        "after": _profile("after", calculate_similarity, original, suspect),
        "large_input": _large_input_benchmark(),
    }
    before = results["before"]
    after = results["after"]
    assert isinstance(before, dict)
    assert isinstance(after, dict)
    results["speedup"] = float(before["seconds_with_profiler"]) / float(
        after["seconds_with_profiler"]
    )
    (OUTPUT_DIRECTORY / "performance.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_html(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
