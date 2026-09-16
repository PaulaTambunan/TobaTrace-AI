"""
search_baseline.py
-------------------
Modul Baseline Search (Tugas 1 / Milestone 1)
Topik Proyek : "TobaTrace" - Sistem Copilot Cerdas Kepatuhan Ekspor &
              Ketertelusuran Kopi Sumatera terhadap EU Deforestation
              Regulation (EUDR Compliance Copilot).

Masalah yang dimodelkan:
    Menentukan rute logistik ber-biaya-minimum dari titik pengumpulan kopi
    petani (farm collection point) di kawasan Danau Toba menuju pelabuhan
    ekspor (Pelabuhan Belawan, Medan), sebagai baseline sebelum agen AI
    (Milestone 4) mengambil alih keputusan routing yang lebih kompleks
    (mempertimbangkan slot inspeksi karantina, dokumen DDS EUDR, dsb).

Formulasi Ruang Keadaan (X, A, T, G, C):
    X (State Space) : Himpunan simpul lokasi rantai pasok kopi
                       (kebun/pengumpul -> pengolahan -> gudang sortasi -> pelabuhan).
    A (Actions)      : Bergerak dari satu simpul ke simpul tetangga yang
                       terhubung jalur darat/angkutan.
    T (Transition)   : T(s, a) -> s' (deterministik, graf tidak berarah).
    G (Goal Test)     : s == "Pelabuhan_Belawan".
    C (Cost)          : Estimasi biaya logistik riil (proxy: jarak tempuh
                       dalam km, merepresentasikan biaya BBM + waktu tempuh).

Algoritma:
    - Uniform Cost Search (UCS)      : uninformed, menjamin optimal.
    - A* Search                       : informed, memakai heuristik jarak
                                         garis-lurus (Haversine) ke pelabuhan
                                         tujuan, yang admissible karena jarak
                                         garis lurus selalu <= jarak jalan riil.

Cara menjalankan:
    uv run python src/search_baseline.py
    (atau)  python src/search_baseline.py
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Representasi Graf Masalah Bisnis
# ---------------------------------------------------------------------------
# Koordinat (lat, lon) — dipakai HANYA untuk menghitung heuristik A*.
# Nilai bersifat perkiraan (approximate), cukup untuk keperluan baseline akademik.
COORDINATES: Dict[str, Tuple[float, float]] = {
    "Kebun_Sitorang":      (2.410, 99.100),   # Klaster kebun kopi petani, Sitorang
    "Balige":              (2.3333, 99.0667), # Kota kecamatan / titik pengumpulan utama
    "Porsea":              (2.3833, 99.1333), # Titik pengumpul alternatif
    "Siborongborong":      (2.2000, 98.9667), # Sentra kopi arabika dataran tinggi
    "Tarutung":            (2.0167, 98.9667), # Kabupaten Tapanuli Utara
    "Parapat":             (2.6667, 98.9333), # Simpul transit tepi Danau Toba
    "Pematangsiantar":     (2.9667, 99.0667), # Unit pengolahan basah (wet mill) regional
    "Tebing_Tinggi":       (3.3286, 99.1625), # Gudang sortasi & pengeringan (dry mill)
    "Medan":               (3.5952, 98.6722), # Hub logistik & bea cukai
    "Pelabuhan_Belawan":   (3.7833, 98.6833), # GOAL: Pelabuhan ekspor
}

# Graf tidak berarah: node -> [(tetangga, biaya_km), ...]
# Biaya = estimasi jarak tempuh darat (km), proxy biaya logistik (Rp/kg setara jarak).
RAW_EDGES: List[Tuple[str, str, float]] = [
    ("Kebun_Sitorang", "Balige", 6),
    ("Kebun_Sitorang", "Porsea", 10),
    ("Balige", "Porsea", 17),
    ("Balige", "Siborongborong", 32),
    ("Kebun_Sitorang", "Pematangsiantar", 95),   # jalur pintas non-resmi, jauh tapi 1 lompatan
    ("Porsea", "Parapat", 38),
    ("Siborongborong", "Tarutung", 24),
    ("Parapat", "Pematangsiantar", 48),
    ("Pematangsiantar", "Tebing_Tinggi", 60),
    ("Tebing_Tinggi", "Medan", 60),
    ("Medan", "Pelabuhan_Belawan", 24),
]


def build_graph(
    edges: List[Tuple[str, str, float]], nodes: Optional[List[str]] = None
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Bangun adjacency list dari daftar edge tidak berarah.
    `nodes` opsional: jika tidak diisi, node diinferensi otomatis dari `edges`
    (memudahkan build_graph dites secara terisolasi tanpa bergantung pada
    variabel global COORDINATES).
    """
    if nodes is None:
        nodes = sorted({n for a, b, _ in edges for n in (a, b)})
    graph: Dict[str, List[Tuple[str, float]]] = {node: [] for node in nodes}
    for a, b, cost in edges:
        graph[a].append((b, cost))
        graph[b].append((a, cost))
    return graph


GRAPH = build_graph(RAW_EDGES, nodes=list(COORDINATES.keys()))

START_NODE = "Kebun_Sitorang"
GOAL_NODE = "Pelabuhan_Belawan"


# ---------------------------------------------------------------------------
# 2. Struktur Hasil Pencarian
# ---------------------------------------------------------------------------
@dataclass
class SearchResult:
    path: List[str]
    total_cost: float
    nodes_expanded: int
    algorithm: str

    def __str__(self) -> str:  # pragma: no cover - hanya untuk tampilan
        rute = " -> ".join(self.path)
        return (
            f"[{self.algorithm}] Rute optimal: {rute}\n"
            f"Total biaya logistik  : {self.total_cost:.2f} km-setara\n"
            f"Jumlah simpul dieksplorasi: {self.nodes_expanded}"
        )


def _reconstruct_path(came_from: Dict[str, Optional[str]], goal: str) -> List[str]:
    path = [goal]
    while came_from[path[-1]] is not None:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# 3. Uniform Cost Search (UCS) - uninformed, menggunakan heapq (Priority Queue)
# ---------------------------------------------------------------------------
def uniform_cost_search(
    graph: Dict[str, List[Tuple[str, float]]], start: str, goal: str
) -> SearchResult:
    frontier: List[Tuple[float, int, str]] = []
    counter = 0  # tie-breaker agar heapq stabil saat cost sama
    heapq.heappush(frontier, (0.0, counter, start))

    came_from: Dict[str, Optional[str]] = {start: None}
    cost_so_far: Dict[str, float] = {start: 0.0}
    expanded = 0

    while frontier:
        current_cost, _, current = heapq.heappop(frontier)
        expanded += 1

        if current == goal:
            return SearchResult(
                path=_reconstruct_path(came_from, goal),
                total_cost=current_cost,
                nodes_expanded=expanded,
                algorithm="Uniform Cost Search (UCS)",
            )

        for neighbor, step_cost in graph[current]:
            new_cost = current_cost + step_cost
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                came_from[neighbor] = current
                counter += 1
                heapq.heappush(frontier, (new_cost, counter, neighbor))

    raise ValueError(f"Tidak ditemukan rute dari {start} ke {goal}")


# ---------------------------------------------------------------------------
# 4. Heuristik A* - Jarak Garis Lurus (Haversine), bersifat admissible
# ---------------------------------------------------------------------------
def haversine_km(coord_a: Tuple[float, float], coord_b: Tuple[float, float]) -> float:
    """Hitung jarak garis lurus antar dua koordinat (lat, lon) dalam km."""
    lat1, lon1 = map(math.radians, coord_a)
    lat2, lon2 = map(math.radians, coord_b)
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    R = 6371.0  # radius bumi (km)
    return R * c


def heuristic(node: str, goal: str = GOAL_NODE) -> float:
    """
    h(n) = jarak garis lurus (km) dari node ke goal.
    Admissible: jarak jalan darat riil >= jarak garis lurus, sehingga h(n)
    tidak pernah melebihi biaya riil menuju goal (tidak overestimate).
    """
    return haversine_km(COORDINATES[node], COORDINATES[goal])


# ---------------------------------------------------------------------------
# 5. A* Search - informed, f(n) = g(n) + h(n)
# ---------------------------------------------------------------------------
def a_star_search(
    graph: Dict[str, List[Tuple[str, float]]], start: str, goal: str
) -> SearchResult:
    frontier: List[Tuple[float, int, str]] = []
    counter = 0
    heapq.heappush(frontier, (heuristic(start, goal), counter, start))

    came_from: Dict[str, Optional[str]] = {start: None}
    g_score: Dict[str, float] = {start: 0.0}
    expanded = 0

    while frontier:
        _, _, current = heapq.heappop(frontier)
        expanded += 1

        if current == goal:
            return SearchResult(
                path=_reconstruct_path(came_from, goal),
                total_cost=g_score[current],
                nodes_expanded=expanded,
                algorithm="A* Search",
            )

        for neighbor, step_cost in graph[current]:
            tentative_g = g_score[current] + step_cost
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                counter += 1
                f_score = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(frontier, (f_score, counter, neighbor))

    raise ValueError(f"Tidak ditemukan rute dari {start} ke {goal}")


# ---------------------------------------------------------------------------
# 6. Eksekusi & Perbandingan
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("TobaTrace - Baseline Search: Rute Logistik Kopi ke Pelabuhan Ekspor")
    print("=" * 70)

    ucs_result = uniform_cost_search(GRAPH, START_NODE, GOAL_NODE)
    print("\n" + str(ucs_result))

    astar_result = a_star_search(GRAPH, START_NODE, GOAL_NODE)
    print("\n" + str(astar_result))

    print("\n" + "-" * 70)
    if abs(ucs_result.total_cost - astar_result.total_cost) < 1e-6:
        print("Validasi: A* mencapai biaya optimal yang SAMA dengan UCS.")
    else:
        print("PERINGATAN: Biaya A* dan UCS berbeda — periksa admissibility heuristik!")
    print(
        f"Efisiensi eksplorasi A* vs UCS: "
        f"{astar_result.nodes_expanded} vs {ucs_result.nodes_expanded} simpul."
    )


if __name__ == "__main__":
    main()