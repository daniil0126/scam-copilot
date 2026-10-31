from __future__ import annotations

from .types import Signal


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


DUPLICATE_TYPES = {"DUPLICATE_EXACT", "DUPLICATE_POTENTIAL", "DUPLICATE_SIMILAR"}


def build_clusters(
    invoice_id: str, signals: list[Signal], current_links: dict[str, list[str]] | None = None,
) -> list[list[str]]:
    """Группирует инвойсы в кластеры дубликатов по парам из rule_b.

    Каждый сигнал DUPLICATE_* несёт evidenceData["refInvoiceId"] — инвойс, на который похож текущий.
    Union-find: если A дублирует B и B дублирует C, все три в одном кластере.
    """
    uf = _UnionFind()
    uf.find(invoice_id)
    for s in signals:
        if s.status != "DETECTED" or s.type not in DUPLICATE_TYPES:
            continue
        ref = s.evidenceData.get("refInvoiceId")
        if not ref:
            continue
        uf.union(invoice_id, ref)

    groups: dict[str, list[str]] = {}
    for node in list(uf.parent.keys()):
        groups.setdefault(uf.find(node), []).append(node)

    return [sorted(g) for g in groups.values() if len(g) >= 2]