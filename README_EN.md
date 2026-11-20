# Guide to Reproducing the Experiments

This package uses random seeds to generate traces of frame arrivals, background blocking, and transmission successes and failures. It reproduces the experiments in the main text of the English report. All policies use the same trace for a given scenario and seed. The simulation requires only a CPU.

## Running the Experiments on Windows

The experiments require Windows. The computer used for the experiments ran Python 3.13.2.

Run the following commands:

```powershell
# Check the Python version and whether the operating system is 32-bit or 64-bit.
py -3.13 -c "import platform, struct; print(platform.python_version(), struct.calcsize('P') * 8)"

# Set up the Python virtual environment. Two folders should then appear: .venv313 and __pycache__.
py -3.13 -m venv .venv313
.\.venv313\Scripts\python.exe -m pip install --upgrade pip
.\.venv313\Scripts\python.exe -m pip install --only-binary=:all: -r .\requirements.txt

# Run the simulation. This creates a folder named results_py313 in the current directory.
.\.venv313\Scripts\python.exe -B .\run_experiment.py --output results_py313
```

## File Locations

| File in the root directory | Purpose |
|---|---|
| `README.md` | Run instructions, experiment scope, and a guide to the results. |
| `requirements.txt` | NumPy and SciPy versions used to reproduce the experiments. |
| `simulator.py` | Generates frames and channel traces, manages the queue, schedules transmissions slot by slot, handles discards and retries, and computes metrics. The main functions are `make_trace`, `burst_trace`, and `simulate`. |
| `run_experiment.py` | Defines the traffic parameters, queue sizes, policies, and seeds for each scenario and runs the experiments in parallel. |
| `statistics_xr.py` | Computes paired comparisons across policies using the same seeds and 95% Student’s t confidence intervals. It also selects the weight subject to the ordinary-frame completion loss budget. |

## Finding the Values Reported in the Paper

By default, the program writes the following files to a new `results/` directory. Each row in an experiment CSV corresponds to one scenario, one seed, and one policy.

| File | Corresponding results in the report |
|---|---|
| `calibration.csv`, `selection.json` | Original and refined grids in Tables 7 and 8, using seeds 4000–4019. The program generates all 540 rows of the combined grid in one run, selects α separately for each candidate set, and then runs the experiment with fresh seeds. The JSON file expresses gains and losses as fractions. Multiply by 100 to convert them to percentage points. The three upper bounds correspond to blocking levels of 30%, 45%, and 60%, respectively. |
| `validation.csv` | Load values in Table 3 and the original main experiment in Figures 2 and 3 and Tables 10–12. Seeds 5000–5029 cover 12 scenarios with independent transmission failures and 1 with correlated failures, giving 3120 rows. |
| `ordering.csv` | Figure 1, the baseline comparisons, and the comparison of ordering rules in Table 6. The file contains 840 rows covering 4 scenarios, 7 policies, and 30 seeds. Policies that also appear in the main experiment use the same set of seeds. |
| `fresh.csv` | Table 9 compares gains in weighted completion and service costs using fresh seeds 6000–6029. With α = 0.125, the value selected in the paper, the file contains 180 rows. |
| `sensitivity.csv` | Comparison of FA0 and EDF in Section 6.3. The experiment covers 20 combinations of frame size variability, transmission failure rate, and blocking rate. Seeds 2000–2029 give 1200 rows. |
| `summary.csv` | Policy means and paired differences for the validation, ordering, fresh-seed, and sensitivity experiments, including confidence intervals and units. The table can be filtered directly in Excel. |

For example, filter `summary.csv` by `dataset=ordering`, `scenario=10`, `left=FA0.125`, `right=FA0`, and `metric=weighted_fraction` to find the mean gain in importance-weighted completion and its confidence interval for the representative scenario. Scenario 10 uses a 4096-packet buffer and 45% blocking. To read the loss in ordinary-frame completion, reverse the sign of the completion difference (new policy minus baseline). Reverse the signs of the interval endpoints as well and swap their order.

In the raw CSV files, `complete_fraction`, `weighted_fraction`, and `low_completion_fraction` give the overall, importance-weighted, and ordinary-frame on-time completion rates, respectively. `wasted_bytes` counts the bytes spent on transmission attempts for frames that ultimately fail. `waste_share` is the fraction of all attempts spent on those frames. The denominator for overall completion includes all generated frames. `trace_sha256` identifies the trace used to pair runs with the same seed. In the summary table, an empty `right` field indicates a single-policy mean. A populated `right` field indicates the difference between the left and right policies on the same trace, calculated as left minus right. The unit `%` denotes percent, and `pp` denotes percentage points.
