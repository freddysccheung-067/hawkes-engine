# Roadmap

The project is built in nine gates. Each gate has an exit test; a gate is done
when that test passes, not when the code is written.

| Gate | Work | Exit test | Status |
|------|------|-----------|--------|
| H0 | Specification, ADRs, CI, package skeleton | Package installs and imports on all three platforms | Done |
| H1 | Reference implementation of likelihood and gradient | Gradient agrees with complex-step differentiation to 1e-10 | Done |
| H2 | C++ likelihood and gradient | Matches the reference implementation to 1e-12 | Next |
| H3 | Estimation (MLE, standard errors) | Recovers known parameters from simulated data within the asymptotic standard errors | — |
| H4 | Simulators (thinning and branching) | Both simulators reproduce the analytic stationary mean | — |
| H5 | Python API and I/O | End-to-end fit of a Parquet file through the public API | — |
| H6 | Trust calibration study | Recovery error mapped across the parameter space | — |
| H7 | Performance | Throughput and memory characterised against the targets | — |
| H8 | Documentation and examples | Docs build warning-free, examples run in CI | — |
| H9 | v0.1.0 release | Wheels on PyPI for all supported platforms | — |

## What "trust calibration" means

Parameter estimates from a Hawkes fit are unreliable in a well-defined region:
when the branching ratio approaches one, $\alpha$ and $\beta$ trade off against
each other and the likelihood becomes flat along a ridge. A fit can converge to
a number that looks precise and is not.

The library's distinguishing feature is a map from parameters to expected
recovery error, so a user can see whether a given fit sits in the trustworthy
region before relying on it. That is built and validated at H6. Until then,
the branching ratio $\rho(\Gamma)$ is reported with every fit, and a value near
one is a warning, not a result.

## Ordering rationale

The reference implementation comes before the fast one so that the fast one has
something to be checked against that it cannot influence. The simulators come
after the likelihood because the likelihood is what the simulation results are
tested with. The trust study comes after everything it measures exists.
