"""Phase 2: distributed optimization, written from scratch in NumPy.

Planned contents
----------------
- ``problems.py``    Loss/gradient definitions: least squares and logistic
                     regression, with optional L2 regularization.
- ``centralized.py`` Centralized baseline solver (all data on one node), used as
                     the reference optimum for the distributed methods.
- ``admm.py``        Consensus ADMM (global-variable consensus form).
- ``dgd.py``         Decentralized gradient descent over a communication graph
                     (mixing matrix built from the topology in the config).
- ``partition.py``   Splitting a dataset across N nodes (IID and non-IID).

Methods are compared on optimality gap, consensus error, iterations,
wall-clock time and bytes exchanged.
"""
