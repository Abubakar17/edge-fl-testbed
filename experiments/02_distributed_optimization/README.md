# Phase 2: Distributed optimization

Distributed least-squares and logistic regression, with consensus ADMM and decentralized
gradient descent implemented from scratch in NumPy. Both are compared against a
centralized solver.

**Questions**
- How quickly each method converges to the centralized optimum (optimality gap and consensus error over iterations).
- How communication rounds and bytes exchanged trade off against accuracy.
- How sensitive each method is to hyperparameters (rho, step size), topology and non-IID partitions.

**Code:** `src/edge_fl/distopt/`
**Config:** [`config.yaml`](config.yaml)
**Outputs:** `results/02_distributed_optimization/`
