"""Across-seed means and paired differences, with pointwise Student t intervals."""
import csv
from collections import defaultdict
from math import sqrt
from statistics import mean, stdev

from scipy.stats import t


RATES = ('complete_fraction', 'weighted_fraction', 'high_completion_fraction',
         'low_completion_fraction', 'waste_share', 'packet_delivery_fraction')


def interval(values):
    values = list(values)
    centre = mean(values)
    half = float(t.ppf(.975, len(values)-1)) * stdev(values) / sqrt(len(values))
    return dict(n=len(values), mean=centre, lower95=centre-half, upper95=centre+half)


def by_scene(rows):
    scenes = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        series = scenes[row['scenario']][row['policy']]
        if row['seed'] in series:
            raise ValueError('Duplicate seed within scenario and policy')
        series[row['seed']] = row
    return scenes


def paired(scene, left, right, metric):
    a, b = scene[left], scene[right]
    if not a or a.keys() != b.keys():
        raise ValueError(f'Unmatched seeds for {left} and {right}')
    values = []
    for seed in sorted(a):
        if a[seed]['trace_sha256'] != b[seed]['trace_sha256']:
            raise ValueError(f'Mismatched traces for seed {seed}')
        values.append(a[seed][metric] - b[seed][metric])
    return values


def select_alpha(rows, candidates):
    scenes = by_scene(rows)
    records = []
    for alpha in candidates:
        label = f'FA{alpha:g}'
        gains, upper = [], []
        for scene in scenes.values():
            gains.extend(paired(scene, label, 'FA0', 'weighted_fraction'))
            loss = paired(scene, 'FA0', label, 'low_completion_fraction')
            upper.append(interval(loss)['upper95'])
        records.append(dict(alpha=alpha, mean_weighted_gain=mean(gains),
                            loss_upper95_by_load=upper, eligible=max(upper) <= .02))
    winner = max((r for r in records if r['eligible']),
                 key=lambda r: (r['mean_weighted_gain'], -r['alpha']))
    return dict(alpha=winner['alpha'], ordinary_loss_budget=.02, candidates=records)


def summarize(datasets, folder, chosen):
    comparisons = {
        'ordering': [('EDF-safe', 'EDF'), ('EDF', 'FIFO'), ('FA0', 'EDF-safe'),
                     ('FA0', 'SRPT-safe'), ('FA0', 'LLF-safe'), ('FA0.125', 'SRPT-safe'),
                     ('FA0.125', 'FA0'), ('FA0.125', 'EDF-safe')],
        'validation': [('FA0.125', 'FA0'), ('FA0.125', 'EDF-safe'), ('FA1', 'FA0'),
                       ('FA0', 'FA0_no_drop'), ('FA1', 'FA1_no_drop')],
        'fresh': [(chosen, 'FA0')],
        'sensitivity': [('FA0', 'EDF')],
    }
    columns = ('dataset', 'scenario', 'capacity', 'background', 'size_cv', 'loss', 'channel',
               'left', 'right', 'metric', 'units', 'n', 'mean', 'lower95', 'upper95')
    with (folder / 'summary.csv').open('x', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for name, rows in datasets.items():
            for scene_id, scene in by_scene(rows).items():
                representative = next(iter(next(iter(scene.values())).values()))
                setting = {k: representative[k] for k in ('capacity','background','size_cv','loss','channel')}
                setting.update(dataset=name, scenario=scene_id)
                for policy, samples in scene.items():
                    for metric in (*RATES, 'load_ratio', 'wasted_bytes'):
                        scale = 100 if metric in RATES else 1
                        units = '%' if metric in RATES else ('ratio' if metric == 'load_ratio' else 'bytes')
                        stats = interval(r[metric]*scale for r in samples.values())
                        writer.writerow(dict(**setting, left=policy, right='', metric=metric, units=units, **stats))
                for left, right in comparisons[name]:
                    for metric in RATES:
                        stats = interval(100*x for x in paired(scene, left, right, metric))
                        writer.writerow(dict(**setting, left=left, right=right, metric=metric, units='pp', **stats))
