# Phase 2: Distributed optimization

Solve one optimization problem in three ways: centralized, consensus ADMM and decentralized
gradient descent. The distributed methods are implemented from scratch in NumPy, and compared
against the centralized solution and against each other, first in simulation and then
across the boards over the Phase 1 gRPC layer.

**Status:** waiting for the problem definition from the supervisor (tracker Q-09). Until
then, the fallback is distributed least squares or logistic regression on synthetic data
(`config.yaml`).

## What the problem needs

- **Separable objective:** `minimize Σᵢ fᵢ(x)`, where node *i* knows only its own `fᵢ`, i.e. its
  local data. ADMM and decentralized GD are built for this form.
- **Convex, ideally with a known or easily computed optimum**, so convergence can be measured
  as a gap to the true solution.
- **Small enough for a 2–4 GB arm64 board:** thousands to hundreds of thousands of samples and
  tens to thousands of variables.
- **Data that can be split in uneven (non-IID) ways,** to study the effect of heterogeneity.

## Questions

- How quickly each method converges to the centralized optimum: optimality gap and
  consensus error over iterations.
- How communication rounds and bytes exchanged trade off against accuracy.
- How sensitive each method is to hyperparameters (ρ, step size), topology and non-IID partitions.
- Wall-clock time on the testbed, compared with the prediction from the Phase 1 model.

## Link to Phase 1

The vectors exchanged here are small (tens to thousands of numbers, up to a few tens of KB).
Phase 1 shows that in this range each message costs a fixed **~1.7 ms when the H3+ serves,
~3.7 ms when an N2L serves**, almost regardless of size. So the cost of a method is set by
**how many communication rounds** it needs, not how many bytes it sends.

**Code:** `src/edge_fl/distopt/`
**Config:** [`config.yaml`](config.yaml)
**Outputs:** `results/02_distributed_optimization/`
