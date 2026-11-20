"""Reproduce the XR scheduling experiments from deterministic traffic and channel traces."""
import argparse
import csv
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

from simulator import Config, burst_trace, make_trace, simulate
from statistics_xr import summarize, select_alpha


LOADS = (.30, .45, .60)
COARSE = (0, .125, .25, .5, 1)
REFINED = (0, .0625, .125, .15625, .1875, .21875, .25, .5, 1)


def fa(alpha):
    return f'FA{alpha:g}'


def run_trace(job):
    scene, config, channel, seed, policies = job
    trace = (burst_trace if channel == 'burst' else make_trace)(config, seed)
    fingerprint = trace.fingerprint()
    rows = []
    for label in policies:
        policy = 'FA' if label.startswith('FA') else label
        alpha = float(label[2:].split('_')[0]) if policy == 'FA' else 0
        metrics = simulate(trace, config, policy, alpha, abandon=not label.endswith('_no_drop'))
        metrics['high_completion_fraction'] = metrics.pop('high_fraction')
        metrics['low_completion_fraction'] = metrics.pop('low_fraction')
        rate = metrics['generated_packets'] / config.duration_s
        capacity = (1000 / config.slot_ms) * (1 - config.background) * (1 - config.loss)
        rows.append(dict(scenario=scene, seed=seed, policy=label, channel=channel,
                         capacity=config.queue_packets, background=config.background,
                         size_cv=config.size_cv, loss=config.loss, trace_sha256=fingerprint,
                         arrival_packets_per_second=rate, load_ratio=rate/capacity, **metrics))
    return rows


def phase(pool, folder, name, scenes, seeds):
    jobs = [(scene, config, channel, seed, policies)
            for scene, config, channel, policies in scenes for seed in seeds]
    rows = []
    with (folder / f'{name}.csv').open('x', newline='', encoding='utf-8') as output:
        writer = None
        for batch in pool.map(run_trace, jobs):
            if writer is None:
                writer = csv.DictWriter(output, fieldnames=list(batch[0]))
                writer.writeheader()
            writer.writerows(batch)
            rows.extend(batch)
    print(f'{name}: {len(rows)} runs', flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results'),
                        help='New directory for the generated CSV and JSON files')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    if args.output.exists():
        parser.error(f'{args.output} already exists; choose a new --output directory')
    args.output.mkdir(parents=True)
    grid = [(i, Config(background=b), 'iid', tuple(map(fa, REFINED))) for i, b in enumerate(LOADS)]
    main_rules = [*map(fa, COARSE), 'FA0_no_drop', 'FA1_no_drop', 'EDF-safe']
    main_scenes = [(i, Config(queue_packets=q, background=b), 'iid', main_rules)
                   for i, (q, b) in enumerate(product((40, 80, 160, 4096), LOADS))]
    main_scenes.append((12, Config(background=.45), 'burst', main_rules))
    ordering = [(i, main_scenes[i][1], 'iid',
                 ('FIFO', 'EDF', 'EDF-safe', 'LLF-safe', 'SRPT-safe', 'FA0', 'FA0.125'))
                for i in (9, 10, 11, 1)]
    sensitivity = [(i, Config(background=b, size_cv=cv, loss=p), 'iid', ('FA0', 'EDF'))
                   for i, (b, cv, p) in enumerate(product((0, .15, .30, .45, .60), (.10, .50), (0, .10)))]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        grid_rows = phase(pool, args.output, 'calibration', grid, range(4000, 4020))
        selection = {name: select_alpha(grid_rows, values) for name, values in
                     [('coarse', COARSE), ('refined', REFINED)]}
        (args.output / 'selection.json').write_text(json.dumps(selection, indent=2), encoding='utf-8')
        chosen = fa(selection['refined']['alpha'])
        fresh_rules = tuple(dict.fromkeys(('FA0', 'FA0.125', chosen)))
        fresh = [(i, c, channel, fresh_rules) for i, c, channel, _ in grid]
        datasets = {
            'validation': phase(pool, args.output, 'validation', main_scenes, range(5000, 5030)),
            'ordering': phase(pool, args.output, 'ordering', ordering, range(5000, 5030)),
            'fresh': phase(pool, args.output, 'fresh', fresh, range(6000, 6030)),
            'sensitivity': phase(pool, args.output, 'sensitivity', sensitivity, range(2000, 2030)),
        }
    summarize(datasets, args.output, chosen)
    print(f'Complete. Results: {args.output.resolve()}')


if __name__ == '__main__':
    main()
