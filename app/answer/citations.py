"""Citations: map the [n] markers in an answer to documents and pages, and drop markers that point nowhere."""
import re

_MARKER = re.compile(r"\[(\d{1,2})\]")
# Other ways models write citations: gpt-oss uses 【1†L1-L5】 or 【4】; some write [1, 2] or [1,3].
_FULLWIDTH = re.compile(r"【\s*(\d{1,2})[^】]*】")
_LIST = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})+)\]")


def normalise_markers(text: str) -> str:
    """Rewrite every citation style into [n] markers: 【1†L1-L5】 -> [1], [1, 2] -> [1][2]."""
    text = _FULLWIDTH.sub(lambda m: f"[{m.group(1)}]", text)
    return _LIST.sub(lambda m: "".join(f"[{n.strip()}]" for n in m.group(1).split(",")), text)


def cited_numbers(text: str, n_sources: int) -> list[int]:
    """Source numbers the answer cites, in order of first use, only those that exist (1..n_sources)."""
    seen = []
    for match in _MARKER.finditer(text):
        n = int(match.group(1))
        if 1 <= n <= n_sources and n not in seen:
            seen.append(n)
    return seen


def remove_invalid_markers(text: str, n_sources: int) -> str:
    """Delete markers like [7] when only 5 sources were given (the model invented them)."""
    return _MARKER.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", text)


def source_list(chunks: list[dict], numbers: list[int]) -> list[dict]:
    """The cited chunks as citations to show under the answer."""
    return [{"n": n, "title": chunks[n - 1]["title"], "publisher": chunks[n - 1].get("publisher", ""),
             "page": chunks[n - 1]["page"], "url": chunks[n - 1]["url"]} for n in numbers]
