# Roadmap

The project is built in nine gates. Each gate has an exit test; a gate is done
when that test passes, not when the code is written.

| Gate | Work | Exit test | Status |
|------|------|-----------|--------|
| H0 | Specification, ADRs, CI, package skeleton | Package installs and imports on all three platforms | Done |
| H1 | Reference implementation of likelihood and gradient | Gradient agrees with complex-step differentiation to 1e-10 | Done |
| H2 | C++ likelihood and gradient | Matches the reference implementation to 1e-12 | Done |
| H3 | Estimation (MLE, standard errors) | Recovers known parameters from simulated data within the asymptotic standard errors | Done |
| H4 | Simulators (thinning and branching) | Both simulators reproduce the analytic stationary mean | Done |
| H5 | Bindings, wheels and packaging | Zero-copy and GIL release proved; wheels build on all three platforms | Done |
| H6 | Trust calibration study | Bias and coverage mapped across the parameter space | Done |
| H7 | Performance | Throughput and memory characterised against the targets | Done |
| H8 | Documentation and examples | Docs build warning-free, examples run in CI | Done |
| H9 | v0.1.0 release | Wheels on PyPI for all supported platforms | Next |

## What "trust calibration" means

Parameter estimates from a Hawkes fit are unreliable in a well-defined region:
when the branching ratio approaches one, $\alpha$ and $\beta$ trade off against
each other and the likelihood becomes flat along a ridge. A fit can converge to
a number that looks precise and is not.

The library's distinguishing feature is a map from parameters to measured
coverage and standard-error honesty, so a user can see what a pre-registered study
found in a regime like theirs. That map was measured at H6 and ships with the
package. What it found is mixed: the reported standard errors understate sampling
spread, and the estimator is undefined in part of the grid (see the Limits page).
The branching ratio $\rho(\Gamma)$ is reported with every fit, and a value near
one is a warning, not a result.

## Ordering rationale

The reference implementation comes before the compiled one so that the compiled one has
something to be checked against that it cannot influence. The simulators come
after the likelihood because the likelihood is what the simulation results are
tested with. The trust study comes after everything it measures exists.
