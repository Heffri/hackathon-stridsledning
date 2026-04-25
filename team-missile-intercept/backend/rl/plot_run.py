"""Post-run plotting for AOE curriculum training.

Reads `rl/runs/<run>/metrics.jsonl` (produced by MetricsCallback) and
the TB event file, emits static PNGs to `rl/runs/<run>/plots/`:

  * reward_curve.png     — ep reward per episode + 100-ep rolling mean
  * win_rate_curve.png   — rolling W/L/D proportions over training
  * fires_stacked_area.png — per-launcher-kind fires over training
                              (detect mode collapse)
  * entropy_curve.png    — ep reward vs step overlaid with entropy_loss
                              trajectory (from TB)
  * hp_histogram.png     — distribution of end-of-ep site HP (all eps)
  * leaks_bar.png        — per-threat-kind leak totals

Run:
  py -3 -m rl.plot_run --run rl/runs/<run_name>

Matplotlib backend defaults to Agg (headless). Tight_layout + sensible
dpi. No data-smoothing beyond the single 100-ep rolling window on the
reward/win curves.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_LAUNCHER_KINDS = ("ciws", "rbs_70", "iris_t_sls", "iris_t_slm", "pac_2", "pac_3")
_THREAT_KINDS = ("drone", "cruise_sub", "ballistic", "hgv")


def _load_jsonl(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _rolling(values: List[float], window: int) -> List[float]:
    if not values:
        return []
    out = []
    from collections import deque
    buf: deque = deque(maxlen=window)
    for v in values:
        buf.append(v)
        out.append(sum(buf) / len(buf))
    return out


def plot_reward_curve(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    steps = [r["step"] for r in records]
    rews = [r["reward"] for r in records]
    roll = _rolling(rews, 100)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(steps, rews, color="#8899aa", alpha=0.4, lw=0.6, label="per-episode")
    ax.plot(steps, roll, color="#1f77b4", lw=1.5, label="rolling 100")
    ax.axhline(0, color="k", lw=0.5, alpha=0.3)
    ax.set_xlabel("env_steps")
    ax.set_ylabel("episode reward")
    ax.set_title("Reward Curve")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_win_rate(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    steps = [r["step"] for r in records]
    win_flags = [1 if r.get("winner") == "blue" else 0 for r in records]
    loss_flags = [1 if r.get("winner") == "red" else 0 for r in records]
    draw_flags = [1 if r.get("winner") in (None, "draw") else 0 for r in records]
    roll_w = _rolling(win_flags, 100)
    roll_l = _rolling(loss_flags, 100)
    roll_d = _rolling(draw_flags, 100)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(steps, roll_w, color="#2ca02c", lw=1.5, label="win")
    ax.plot(steps, roll_l, color="#d62728", lw=1.5, label="loss")
    ax.plot(steps, roll_d, color="#ff7f0e", lw=1.5, label="draw/truncated")
    ax.set_xlabel("env_steps")
    ax.set_ylabel("rolling rate (100 ep)")
    ax.set_title("Win / Loss / Draw Rate")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_fires_stacked_area(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    steps = [r["step"] for r in records]
    per_kind = {k: [] for k in _LAUNCHER_KINDS}
    for r in records:
        fbk = r.get("fires_by_kind") or {}
        for k in _LAUNCHER_KINDS:
            per_kind[k].append(fbk.get(k, 0))
    # 100-ep rolling mean for smoothness.
    smoothed = {k: _rolling(per_kind[k], 100) for k in _LAUNCHER_KINDS}
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.stackplot(
        steps,
        [smoothed[k] for k in _LAUNCHER_KINDS],
        labels=list(_LAUNCHER_KINDS),
        alpha=0.85,
    )
    ax.set_xlabel("env_steps")
    ax.set_ylabel("fires per episode (rolling 100)")
    ax.set_title("Fires per Launcher Kind (collapse detector)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_hp_histogram(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    hps = [r.get("site_hp_end", 0) for r in records[-500:]]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(hps, bins=30, color="#1f77b4", alpha=0.8)
    ax.set_xlabel("end-of-episode total site HP")
    ax.set_ylabel("count (last 500 eps)")
    ax.set_title("Site HP at Episode End")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_leaks_bar(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    tot = Counter()
    for r in records:
        for k, v in (r.get("leaks_by_kind") or {}).items():
            tot[k] += v
    kinds = [k for k in _THREAT_KINDS]
    vals = [tot.get(k, 0) for k in kinds]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(kinds, vals, color=["#6baed6", "#fd8d3c", "#c7e9c0", "#d62728"])
    ax.set_ylabel("total leaks across all eps")
    ax.set_title("Leaks by Threat Kind")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_intercepts_bar(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    tot = Counter()
    for r in records:
        for k, v in (r.get("intercepts_by_kind") or {}).items():
            tot[k] += v
    kinds = [k for k in _THREAT_KINDS]
    vals = [tot.get(k, 0) for k in kinds]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(kinds, vals, color=["#2ca02c", "#17becf", "#9467bd", "#8c564b"])
    ax.set_ylabel("total intercepts across all eps")
    ax.set_title("Intercepts by Threat Kind")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_sim_t_curve(records: List[dict], out_path: Path) -> None:
    if not records:
        return
    steps = [r["step"] for r in records]
    sim_t = [r.get("sim_t", 0.0) for r in records]
    roll = _rolling(sim_t, 100)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(steps, sim_t, color="#8899aa", alpha=0.3, lw=0.5)
    ax.plot(steps, roll, color="#9467bd", lw=1.5, label="rolling 100")
    ax.set_xlabel("env_steps")
    ax.set_ylabel("sim_t at episode end (s)")
    ax.set_title("Episode Length (short = decisive, long = attrition)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="rl/runs/<run_name> dir")
    args = ap.parse_args()
    run_dir = Path(args.run)
    jsonl = run_dir / "metrics.jsonl"
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    records = _load_jsonl(jsonl)
    print(f"[plot_run] loaded {len(records)} episode records from {jsonl}")
    if not records:
        print(f"[plot_run] no records — did MetricsCallback run?")
        return

    plot_reward_curve(records, plots_dir / "reward_curve.png")
    plot_win_rate(records, plots_dir / "win_rate_curve.png")
    plot_fires_stacked_area(records, plots_dir / "fires_stacked_area.png")
    plot_hp_histogram(records, plots_dir / "hp_histogram.png")
    plot_leaks_bar(records, plots_dir / "leaks_bar.png")
    plot_intercepts_bar(records, plots_dir / "intercepts_bar.png")
    plot_sim_t_curve(records, plots_dir / "sim_t_curve.png")
    print(f"[plot_run] wrote 7 PNGs to {plots_dir}")


if __name__ == "__main__":
    main()
