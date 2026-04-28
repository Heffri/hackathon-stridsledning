"""Cross-evaluation tournament runner — plays a Red × Blue policy matrix.

For each (red_spec, blue_spec) pair in the provided cross product, runs
``n_episodes`` episodes on a fixed seed list and aggregates results. Same
seeds are re-used across pairs so matchup comparisons are paired (seed N
produces identical initial world state across every pair — rule RedAI's
private rng is reseeded from the env seed, and RedEnv.reset uses the
seed for Red learned-env rng too).

Writes two outputs:

  * ``--out-json``: full per-episode + per-pair rollup, machine-readable.
  * ``--out-md``: human-readable report (matrix table + per-pair detail).

CLI (example):

    python -m rl.cross_eval_tournament ^
      --seeds 1000-1029 ^
      --red-policies "rule,rl/runs/red_20260421_205051/model.zip,rl/runs/red_20260421_234425/model.zip" ^
      --blue-policies "rule,rl/models/blue_ai_1m_2xpenalty/model.zip" ^
      --out-json tournament_3x2_2026-04-22.json ^
      --out-md tournament_3x2_2026-04-22.md

Paths in ``--red-policies`` / ``--blue-policies`` are interpreted relative
to the process cwd (typically ``backend/``).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from rl.cross_eval import (
    CrossEvalEnv,
    EpisodeResult,
    RULE_SENTINEL,
)


# ----------------------------------------------------------------------
# CLI parsing helpers
# ----------------------------------------------------------------------
def parse_seeds(s: str) -> List[int]:
    """Accepts ``"1000-1029"`` (inclusive range) or ``"a,b,c"`` comma list.

    Mixed forms are not supported (keep it simple).
    """
    s = s.strip()
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", s)
    if m:
        lo = int(m.group(1))
        hi = int(m.group(2))
        if hi < lo:
            raise ValueError(f"--seeds range {s} has lo > hi")
        return list(range(lo, hi + 1))
    if "," in s:
        return [int(x.strip()) for x in s.split(",") if x.strip()]
    return [int(s)]


def parse_specs(s: str) -> List[str]:
    """Splits a comma list of policy specs. ``"rule"`` stays as the
    sentinel; other entries are paths, returned as-is."""
    return [x.strip() for x in s.split(",") if x.strip()]


def label_of(spec: str) -> str:
    """Short human label derived from a policy spec.

    * ``"rule"`` → ``"rule"``
    * ``".../runs/red_20260421_205051/model.zip"`` → ``"red_20260421_205051"``
    * ``".../models/blue_ai_1m_2xpenalty/model.zip"`` → ``"blue_ai_1m_2xpenalty"``
    * Any other path → basename of the parent directory (so co-located
      model.zip files still get a meaningful label).
    """
    if spec == RULE_SENTINEL:
        return "rule"
    p = pathlib.Path(spec)
    if p.name == "model.zip":
        return p.parent.name
    return p.stem


# ----------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------
@dataclass
class PairStats:
    red_label: str
    blue_label: str
    red_spec: str
    blue_spec: str
    n_episodes: int
    # Win / loss / draw counts
    red_wins: int
    blue_wins: int
    draws: int
    # Means (with stdev when n > 1)
    episode_length_mean: float
    episode_length_std: float
    sim_time_mean: float
    sim_time_std: float
    sites_destroyed_mean: float
    sites_destroyed_std: float
    sites_total_damage_mean: float
    sites_total_damage_std: float
    red_budget_remaining_mean: float
    blue_budget_remaining_mean: float
    intercepts_mean: float
    leaks_mean: float
    ground_crashes_mean: float
    # Aggregate per-kind totals across all episodes
    red_spawns_total_by_kind: Dict[str, int] = field(default_factory=dict)
    blue_launches_total_by_kind: Dict[str, int] = field(default_factory=dict)
    # Wall-clock
    wall_s: float = 0.0

    @property
    def red_win_rate(self) -> float:
        return self.red_wins / max(1, self.n_episodes)

    @property
    def blue_win_rate(self) -> float:
        return self.blue_wins / max(1, self.n_episodes)

    @property
    def draw_rate(self) -> float:
        return self.draws / max(1, self.n_episodes)


def _safe_std(xs: Sequence[float]) -> float:
    """stdev that returns 0.0 for n < 2 (statistics.stdev raises)."""
    if len(xs) < 2:
        return 0.0
    return float(statistics.stdev(xs))


def _safe_mean(xs: Sequence[float]) -> float:
    return float(statistics.mean(xs)) if xs else 0.0


def aggregate(
    red_spec: str,
    blue_spec: str,
    results: Sequence[EpisodeResult],
    wall_s: float,
) -> PairStats:
    n = len(results)
    red_wins = sum(1 for r in results if r.winner == "red")
    blue_wins = sum(1 for r in results if r.winner == "blue")
    draws = sum(1 for r in results if r.winner == "draw")

    lens = [r.episode_length for r in results]
    sims = [r.sim_time for r in results]
    sdests = [r.sites_destroyed for r in results]
    sdmgs = [r.sites_total_damage for r in results]
    rbuds = [r.red_budget_remaining for r in results]
    bbuds = [r.blue_budget_remaining for r in results]
    ints = [r.intercept_count for r in results]
    leaks = [r.leak_count for r in results]
    gcs = [r.ground_crash_count for r in results]

    red_spawns_total: Dict[str, int] = {}
    blue_launches_total: Dict[str, int] = {}
    for r in results:
        for k, v in r.red_spawns_by_kind.items():
            red_spawns_total[k] = red_spawns_total.get(k, 0) + v
        for k, v in r.blue_launches_by_kind.items():
            blue_launches_total[k] = blue_launches_total.get(k, 0) + v

    return PairStats(
        red_label=label_of(red_spec),
        blue_label=label_of(blue_spec),
        red_spec=red_spec,
        blue_spec=blue_spec,
        n_episodes=n,
        red_wins=red_wins,
        blue_wins=blue_wins,
        draws=draws,
        episode_length_mean=_safe_mean(lens),
        episode_length_std=_safe_std(lens),
        sim_time_mean=_safe_mean(sims),
        sim_time_std=_safe_std(sims),
        sites_destroyed_mean=_safe_mean(sdests),
        sites_destroyed_std=_safe_std(sdests),
        sites_total_damage_mean=_safe_mean(sdmgs),
        sites_total_damage_std=_safe_std(sdmgs),
        red_budget_remaining_mean=_safe_mean(rbuds),
        blue_budget_remaining_mean=_safe_mean(bbuds),
        intercepts_mean=_safe_mean(ints),
        leaks_mean=_safe_mean(leaks),
        ground_crashes_mean=_safe_mean(gcs),
        red_spawns_total_by_kind=red_spawns_total,
        blue_launches_total_by_kind=blue_launches_total,
        wall_s=wall_s,
    )


# ----------------------------------------------------------------------
# Pair runner
# ----------------------------------------------------------------------
def run_pair(
    red_spec: str,
    blue_spec: str,
    seeds: Sequence[int],
    episode_time_limit: float,
    verbose: bool = True,
) -> Tuple[List[EpisodeResult], float]:
    """Run ``len(seeds)`` episodes of the given pair. Returns
    ``(list_of_results, wall_clock_seconds)``. One ``CrossEvalEnv`` instance
    is constructed and reused — policies are loaded once per pair.
    """
    r_lab = label_of(red_spec)
    b_lab = label_of(blue_spec)
    if verbose:
        print(
            f"\n=== pair: {r_lab}  vs  {b_lab}  ({len(seeds)} eps) ==="
        )
    t0 = time.time()
    env = CrossEvalEnv(
        red_spec=red_spec,
        blue_spec=blue_spec,
        seed=seeds[0],
        episode_time_limit=episode_time_limit,
    )
    results: List[EpisodeResult] = []
    for i, seed in enumerate(seeds):
        t_ep = time.time()
        r = env.run_episode(seed=seed)
        results.append(r)
        if verbose:
            dt = time.time() - t_ep
            print(
                f"  ep {i+1:2d}/{len(seeds):2d} seed={seed:5d} -> "
                f"winner={r.winner:5s} len={r.episode_length:4d} "
                f"sim={r.sim_time:5.1f}s dmg={r.sites_total_damage:4d} "
                f"sites_dead={r.sites_destroyed} | {dt:4.1f}s"
            )
    wall = time.time() - t0
    if verbose:
        print(
            f"  pair wall: {wall:5.1f}s "
            f"({wall/len(seeds):4.1f}s / ep)"
        )
    return results, wall


# ----------------------------------------------------------------------
# Output writers
# ----------------------------------------------------------------------
def _cell_summary(ps: PairStats) -> str:
    """One-line cell summary for the matrix table."""
    return (
        f"R {ps.red_win_rate*100:.0f}% / "
        f"B {ps.blue_win_rate*100:.0f}% / "
        f"D {ps.draw_rate*100:.0f}%<br/>"
        f"len {ps.episode_length_mean:.0f} · "
        f"dmg {ps.sites_total_damage_mean:.0f} · "
        f"sites_dead {ps.sites_destroyed_mean:.2f}"
    )


def write_md(
    pairs: Dict[Tuple[str, str], PairStats],
    red_labels: Sequence[str],
    blue_labels: Sequence[str],
    n_episodes: int,
    seeds: Sequence[int],
    episode_time_limit: float,
    path: pathlib.Path,
) -> None:
    """Human-readable tournament report."""
    lines: List[str] = []
    lines.append("# Cross-eval tournament — Red × Blue matrix")
    lines.append("")
    lines.append(f"- Episodes per pair: **{n_episodes}**")
    lines.append(
        f"- Seed list: {seeds[0]}–{seeds[-1]} ({len(seeds)} seeds, "
        f"shared across every pair)"
    )
    lines.append(f"- Episode time limit: {episode_time_limit:.0f}s sim")
    lines.append("")
    # Matrix
    lines.append("## Results matrix")
    lines.append("")
    header = "| Red \\ Blue | " + " | ".join(blue_labels) + " |"
    sep = "|---" * (len(blue_labels) + 1) + "|"
    lines.append(header)
    lines.append(sep)
    for r_lab in red_labels:
        row_cells = [r_lab]
        for b_lab in blue_labels:
            ps = pairs.get((r_lab, b_lab))
            row_cells.append(_cell_summary(ps) if ps else "–")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")
    lines.append(
        "_Cell legend:_ `R% / B% / D%` is Red wins / Blue wins / draws "
        "over the n episodes. `len` = mean episode length in decisions "
        "(1 decision = 0.5s sim). `dmg` = mean total HP damage across "
        "all sites. `sites_dead` = mean count of sites with HP=0."
    )
    lines.append("")
    # Detailed per-pair stats
    lines.append("## Per-pair detail")
    lines.append("")
    for r_lab in red_labels:
        for b_lab in blue_labels:
            ps = pairs.get((r_lab, b_lab))
            if ps is None:
                continue
            lines.append(f"### {r_lab}  vs  {b_lab}")
            lines.append("")
            lines.append(f"- Red spec: `{ps.red_spec}`")
            lines.append(f"- Blue spec: `{ps.blue_spec}`")
            lines.append(f"- Episodes: {ps.n_episodes}")
            lines.append(
                f"- Winner breakdown: Red **{ps.red_wins}** "
                f"({ps.red_win_rate*100:.1f}%) · "
                f"Blue **{ps.blue_wins}** ({ps.blue_win_rate*100:.1f}%) · "
                f"Draw **{ps.draws}** ({ps.draw_rate*100:.1f}%)"
            )
            lines.append(
                f"- Episode length: {ps.episode_length_mean:.1f} ± "
                f"{ps.episode_length_std:.1f} decisions"
            )
            lines.append(
                f"- Sim time: {ps.sim_time_mean:.1f} ± "
                f"{ps.sim_time_std:.1f} s"
            )
            lines.append(
                f"- Sites destroyed: {ps.sites_destroyed_mean:.2f} ± "
                f"{ps.sites_destroyed_std:.2f}"
            )
            lines.append(
                f"- Total site damage: {ps.sites_total_damage_mean:.1f} ± "
                f"{ps.sites_total_damage_std:.1f}"
            )
            lines.append(
                f"- Red budget remaining: "
                f"${ps.red_budget_remaining_mean/1e6:.1f}M mean"
            )
            lines.append(
                f"- Blue budget remaining: "
                f"${ps.blue_budget_remaining_mean/1e6:.1f}M mean"
            )
            lines.append(
                f"- Events (per-episode mean): "
                f"intercepts {ps.intercepts_mean:.1f} · "
                f"leaks {ps.leaks_mean:.1f} · "
                f"ground crashes {ps.ground_crashes_mean:.1f}"
            )
            if ps.red_spawns_total_by_kind:
                kind_bits = [
                    f"{k}: {v}"
                    for k, v in sorted(
                        ps.red_spawns_total_by_kind.items(),
                        key=lambda kv: -kv[1],
                    )
                    if v
                ]
                if kind_bits:
                    lines.append(
                        "- Red spawn totals (all eps): "
                        + ", ".join(kind_bits)
                    )
            if ps.blue_launches_total_by_kind:
                kind_bits = [
                    f"{k}: {v}"
                    for k, v in sorted(
                        ps.blue_launches_total_by_kind.items(),
                        key=lambda kv: -kv[1],
                    )
                    if v
                ]
                if kind_bits:
                    lines.append(
                        "- Blue launch totals (all eps): "
                        + ", ".join(kind_bits)
                    )
            lines.append(f"- Wall clock: {ps.wall_s:.1f}s")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(
    pairs: Dict[Tuple[str, str], PairStats],
    per_episode: Dict[Tuple[str, str], List[EpisodeResult]],
    red_labels: Sequence[str],
    blue_labels: Sequence[str],
    n_episodes: int,
    seeds: Sequence[int],
    episode_time_limit: float,
    path: pathlib.Path,
) -> None:
    """Machine-readable full dump."""
    payload = {
        "meta": {
            "n_episodes": n_episodes,
            "seeds": list(seeds),
            "episode_time_limit": episode_time_limit,
            "red_labels": list(red_labels),
            "blue_labels": list(blue_labels),
        },
        "pairs": [],
    }
    for r_lab in red_labels:
        for b_lab in blue_labels:
            key = (r_lab, b_lab)
            ps = pairs.get(key)
            if ps is None:
                continue
            ep_list = per_episode.get(key, [])
            payload["pairs"].append({
                "red": r_lab,
                "blue": b_lab,
                "stats": asdict(ps),
                "episodes": [e.to_dict() for e in ep_list],
            })
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Cross-evaluation tournament — run a Red × Blue policy matrix."
        )
    )
    ap.add_argument(
        "--n-episodes", type=int, default=30,
        help="Episodes per pair (ignored if --seeds is a range or list).",
    )
    ap.add_argument(
        "--seeds", type=str, default=None,
        help="Seed list: ``LO-HI`` (inclusive range) or ``a,b,c``. "
             "Default: [1000, 1000+n_episodes).",
    )
    ap.add_argument(
        "--red-policies", type=str, required=True,
        help='Comma list of Red specs. Use "rule" for rule-based Red.',
    )
    ap.add_argument(
        "--blue-policies", type=str, required=True,
        help='Comma list of Blue specs. Use "rule" for rule-based Blue.',
    )
    ap.add_argument(
        "--episode-time-limit", type=float, default=600.0,
        help="Max sim seconds per episode. Default matches training.",
    )
    ap.add_argument("--out-json", type=str, default=None)
    ap.add_argument("--out-md", type=str, default=None)
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress per-episode log.")
    args = ap.parse_args()

    if args.seeds is None:
        seeds = list(range(1000, 1000 + args.n_episodes))
    else:
        seeds = parse_seeds(args.seeds)
    n_episodes = len(seeds)

    red_specs = parse_specs(args.red_policies)
    blue_specs = parse_specs(args.blue_policies)

    red_labels = [label_of(s) for s in red_specs]
    blue_labels = [label_of(s) for s in blue_specs]

    total_pairs = len(red_specs) * len(blue_specs)
    print(
        f"Tournament: {len(red_specs)} Red × {len(blue_specs)} Blue "
        f"= {total_pairs} pairs, {n_episodes} eps each "
        f"= {total_pairs * n_episodes} episodes total"
    )
    print(f"Red labels:  {red_labels}")
    print(f"Blue labels: {blue_labels}")

    pairs: Dict[Tuple[str, str], PairStats] = {}
    per_episode: Dict[Tuple[str, str], List[EpisodeResult]] = {}
    t_total = time.time()
    for red_spec in red_specs:
        for blue_spec in blue_specs:
            r_lab = label_of(red_spec)
            b_lab = label_of(blue_spec)
            results, wall = run_pair(
                red_spec, blue_spec, seeds,
                episode_time_limit=args.episode_time_limit,
                verbose=not args.quiet,
            )
            ps = aggregate(red_spec, blue_spec, results, wall_s=wall)
            pairs[(r_lab, b_lab)] = ps
            per_episode[(r_lab, b_lab)] = results
            print(
                f"[pair] {r_lab:22s} vs {b_lab:22s}  "
                f"R={ps.red_wins}/{ps.n_episodes} ({ps.red_win_rate*100:.0f}%) "
                f"B={ps.blue_wins}/{ps.n_episodes} ({ps.blue_win_rate*100:.0f}%) "
                f"D={ps.draws}/{ps.n_episodes} ({ps.draw_rate*100:.0f}%)"
            )
    total_wall = time.time() - t_total
    print(f"\n=== Tournament done in {total_wall:.1f}s "
          f"({total_wall/60:.1f} min) ===")

    if args.out_json:
        p = pathlib.Path(args.out_json)
        write_json(
            pairs, per_episode,
            red_labels, blue_labels,
            n_episodes, seeds, args.episode_time_limit,
            p,
        )
        print(f"JSON results -> {p}")
    if args.out_md:
        p = pathlib.Path(args.out_md)
        write_md(
            pairs,
            red_labels, blue_labels,
            n_episodes, seeds, args.episode_time_limit,
            p,
        )
        print(f"Markdown report -> {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
