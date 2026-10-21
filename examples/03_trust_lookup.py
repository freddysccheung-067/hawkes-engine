"""The three answers trust_lookup can give, one query each.

Queries use the anchor cell of the H6 study: N = 2000, rho = 0.3028, beta_min = 1,
T = 1722.6. Nothing is fitted; the lookup reads the shipped map of measured
cells. Deterministic and instant.
"""

import hawkes_engine as he


def show(label, answer):
    print(f"{label}\n  status: {answer.status}")
    if answer.cell:
        print(f"  nearest cell: {answer.cell}, distance {answer.distance:.3f} grid steps")
    if answer.coverage:
        cov, se = answer.coverage["all"]
        print(f"  coverage of nominal-95% intervals, all coordinates: {cov:.3f} +/- {se:.3f}")
        for block in ("mu", "alpha", "beta"):
            q, qse = answer.q[block]
            print(f"  q[{block}] = mean reported SE / empirical SD: {q:.3f} +/- {qse:.3f}")
    if answer.no_se_rate is not None:
        print(f"  fits with no standard error in that cell: {answer.no_se_rate:.3f}")
    print(f"  note: {answer.note}\n")


# Inside the measured box, estimator defined: coverage and q are reported.
show("measured", he.trust_lookup(N=2000, rho_hat=0.3028, beta=1.0, T=1722.6))

# Inside the box, but the window holds 1.7 decay times (beta * T = 1.7): the
# estimator was undefined there, so the map reports no coverage number.
show("estimator undefined", he.trust_lookup(N=2000, rho_hat=0.3028, beta=1.0, T=1.7))

# Outside the box (N above 50 000): the map does not extrapolate.
show("unknown", he.trust_lookup(N=500_000, rho_hat=0.3028, beta=1.0, T=1722.6))
