"""Mesin CSP generik: AC-3 + Backtracking (MRV, forward checking, branch & bound).

Tidak bergantung pada domain dokumen sehingga dapat diuji terpisah.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

Predicate = Callable[[Any, Any], bool]
Domains = Dict[str, List[Any]]


@dataclass
class SearchStats:
    ac3_revisions: int = 0
    ac3_removed: int = 0
    ac3_time: float = 0.0
    nodes: int = 0
    backtracks: int = 0
    solutions_found: int = 0
    search_time: float = 0.0
    timed_out: bool = False
    wipeout: Optional[Tuple[str, str, str]] = None  # (variabel, tetangga, nama batasan)


class _LimitReached(Exception):
    pass


class CSP:
    """Variabel -> domain, plus batasan biner bernama."""

    def __init__(self) -> None:
        self.domains: Domains = {}
        self._cons: Dict[Tuple[str, str], List[Tuple[str, Predicate]]] = defaultdict(list)
        self.neighbors: Dict[str, set] = defaultdict(set)

    def add_variable(self, name: str, domain: List[Any]) -> None:
        if name in self.domains:
            raise ValueError(f"variabel duplikat: {name}")
        self.domains[name] = list(domain)

    def add_constraint(self, a: str, b: str, pred: Predicate, name: str) -> None:
        if a == b:
            raise ValueError("batasan biner memerlukan dua variabel berbeda")
        if a not in self.domains or b not in self.domains:
            raise KeyError("variabel belum didefinisikan")
        self._cons[(a, b)].append((name, pred))
        self._cons[(b, a)].append((name, lambda y, x, p=pred: p(x, y)))
        self.neighbors[a].add(b)
        self.neighbors[b].add(a)

    def violated(self, a: str, va: Any, b: str, vb: Any) -> Optional[str]:
        """Nama batasan pertama yang dilanggar, atau None bila konsisten."""
        for name, pred in self._cons.get((a, b), ()):
            if not pred(va, vb):
                return name
        return None

    def arcs(self) -> List[Tuple[str, str]]:
        return list(self._cons.keys())


def _revise(csp: CSP, doms: Domains, xi: str, xj: str, stats: SearchStats):
    keep, reasons = [], Counter()
    for vx in doms[xi]:
        supported, first = False, None
        for vy in doms[xj]:
            n = csp.violated(xi, vx, xj, vy)
            if n is None:
                supported = True
                break
            if first is None:
                first = n
        if supported:
            keep.append(vx)
        else:
            reasons[first or "domain_tetangga_kosong"] += 1
    removed = len(doms[xi]) - len(keep)
    stats.ac3_revisions += 1
    if removed:
        doms[xi] = keep
        stats.ac3_removed += removed
    return removed, reasons


def ac3(csp: CSP, doms: Domains, stats: Optional[SearchStats] = None) -> bool:
    """Arc consistency AC-3. Memodifikasi `doms`. False bila ada domain kosong."""
    stats = stats if stats is not None else SearchStats()
    t0 = time.perf_counter()
    queue = deque(csp.arcs())
    while queue:
        xi, xj = queue.popleft()
        removed, reasons = _revise(csp, doms, xi, xj, stats)
        if removed:
            if not doms[xi]:
                top = reasons.most_common(1)[0][0] if reasons else "?"
                stats.wipeout = (xi, xj, top)
                stats.ac3_time += time.perf_counter() - t0
                return False
            for xk in csp.neighbors[xi]:
                if xk != xj:
                    queue.append((xk, xi))
    stats.ac3_time += time.perf_counter() - t0
    return True


def backtracking_search(
    csp: CSP,
    doms: Domains,
    *,
    use_mrv: bool = True,
    use_fc: bool = True,
    score: Optional[Callable[[str, Any], float]] = None,
    optimize: bool = False,
    node_limit: Optional[int] = None,
    stats: Optional[SearchStats] = None,
) -> Optional[Dict[str, Any]]:
    """Backtracking dengan MRV (+ derajat sebagai tie-break) dan forward checking.

    optimize=True: branch & bound, memaksimalkan jumlah `score` semua variabel.
    """
    stats = stats if stats is not None else SearchStats()
    order = list(csp.domains.keys())
    best: Dict[str, Any] = {"assign": None, "score": float("-inf")}
    t0 = time.perf_counter()

    def val_score(v: str, x: Any) -> float:
        return score(v, x) if score else 0.0

    def rec(assign: Dict[str, Any], d: Domains, cur: float) -> bool:
        unassigned = [v for v in order if v not in assign]
        if not unassigned:
            stats.solutions_found += 1
            if cur > best["score"]:
                best["assign"], best["score"] = dict(assign), cur
            return not optimize
        if optimize and score and best["assign"] is not None:
            ub = cur + sum(max(val_score(v, x) for x in d[v]) for v in unassigned)
            if ub <= best["score"] + 1e-12:
                return False
        if use_mrv:
            var = min(unassigned, key=lambda v: (
                len(d[v]), -sum(1 for n in csp.neighbors[v] if n not in assign)))
        else:
            var = unassigned[0]
        values = sorted(d[var], key=lambda x: -val_score(var, x)) if score else list(d[var])
        for val in values:
            stats.nodes += 1
            if node_limit is not None and stats.nodes > node_limit:
                raise _LimitReached
            if use_fc:
                nd = dict(d)
                nd[var] = [val]
                ok = True
                for n in csp.neighbors[var]:
                    if n in assign:
                        continue
                    filt = [w for w in d[n] if csp.violated(var, val, n, w) is None]
                    if not filt:
                        ok = False
                        break
                    nd[n] = filt
                if not ok:
                    stats.backtracks += 1
                    continue
            else:
                if any(csp.violated(var, val, n, assign[n]) is not None
                       for n in csp.neighbors[var] if n in assign):
                    stats.backtracks += 1
                    continue
                nd = d
            assign[var] = val
            done = rec(assign, nd, cur + val_score(var, val))
            del assign[var]
            if done:
                return True
            stats.backtracks += 1
        return False

    try:
        rec({}, {k: list(v) for k, v in doms.items()}, 0.0)
    except _LimitReached:
        stats.timed_out = True
        if not optimize:
            best["assign"] = None
    stats.search_time += time.perf_counter() - t0
    return best["assign"]
