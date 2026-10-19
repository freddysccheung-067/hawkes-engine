// SPDX-License-Identifier: MIT
//
// Likelihood and gradient, one pass over the event stream.
//
// The state carried between events (all row-major M*M, cell (i, j) with i the
// target and j the source) is:
//
//   S_ij(t) = sum_m exp(-beta_ij (t - t_m))            mathematics.md section 4
//   U_ij(t) = sum_m (t - t_m) exp(-beta_ij (t - t_m))  = -dS_ij/dbeta
//
// A gap of dt multiplies every term by exp(-beta dt) and adds dt to every age:
//
//   S <- e * S
//   U <- e * (U + dt * S)
//
// Both are forward substitutions with non-negative terms, so neither loses
// precision through cancellation. U is what the beta derivative of the event
// term needs.
//
// The compensator terms are a second, independent pass, because they depend on
// the distance from each event to T rather than to the next event:
//
//   C_ij(T) = sum_m (1 - exp(-beta_ij (T - t_m)))
//   Q_ij(T) = sum_m [1 - (1 + x_m) exp(-x_m)],  x_m = beta_ij (T - t_m)
//
// The compensator is mu_i T + sum_j (alpha_ij/beta_ij) C_ij(T); its beta
// derivative is alpha_ij Q_ij(T) / beta_ij^2. Q must be accumulated term by
// term. Recovering it as C - beta*U would subtract two quantities of size
// O(N x) to leave one of size O(N x^2/2), throwing away log-accuracy when
// beta_ij (T - t_m) is small; that is exactly the regime of a slow decay over
// a short window.

#include "hawkes/workspace.hpp"

#include <cmath>
#include <cstddef>
#include <limits>

#include "hawkes/kernel_exp.hpp"

namespace hawkes {

namespace {

// 1 - (1 + x) exp(-x) for x >= 0, without cancellation.
//
// For x >= 0.5 the direct form -x - (1+x)*expm1(-x) is accurate: it is written
// with expm1 so the correction term carries full relative precision, and the
// subtraction loses at most a factor 1/x.
//
// Below 0.5 the two pieces are nearly the same size, so use the Maclaurin
// series, which converges in a handful of terms there:
//
//   1 - (1+x)e^-x = sum_{m >= 2} (-x)^m (m - 1) / m!
[[nodiscard]] Real one_minus_one_plus_x_decay(Real x) noexcept {
    if (x >= 0.5) {
        return -x - (1.0 + x) * std::expm1(-x);
    }
    Real sum  = 0.5 * x * x;
    Real term = sum;
    for (int m = 2; m < 40; ++m) {
        // term_{m+1} / term_m = -x * m / ((m + 1)(m - 1))
        term *= -x * static_cast<Real>(m) /
                (static_cast<Real>(m + 1) * static_cast<Real>(m - 1));
        sum += term;
        if (std::abs(term) <= std::numeric_limits<Real>::epsilon() * std::abs(sum)) {
            break;
        }
    }
    return sum;
}

inline std::size_t cell(Index i, Index j, Index M) noexcept {
    return static_cast<std::size_t>(i) * static_cast<std::size_t>(M) +
           static_cast<std::size_t>(j);
}

constexpr Real kNaN = std::numeric_limits<Real>::quiet_NaN();
constexpr Real kNegInf = -std::numeric_limits<Real>::infinity();

}  // namespace

// ---------------------------------------------------------------------------
// Pair parameterization
// ---------------------------------------------------------------------------

PairWorkspace::PairWorkspace(Index M)
    : M_(M),
      MM_(static_cast<std::size_t>(M) * static_cast<std::size_t>(M)),
      S_(MM_, 0.0),
      U_(MM_, 0.0),
      C_(MM_, 0.0),
      Q_(MM_, 0.0) {}

Real PairWorkspace::evaluate(const EventView& ev, const ParamView& p, Real T, Gradient* grad) {
    const Index       M     = M_;
    const std::size_t MMsiz = MM_;
    const Real*       mu    = p.mu;
    const Real*       al    = p.alpha;
    const Real*       be    = p.beta;

    for (std::size_t k = 0; k < MMsiz; ++k) {
        S_[k] = 0.0;
        U_[k] = 0.0;
    }
    if (grad != nullptr) {
        for (Index i = 0; i < M; ++i) {
            grad->dmu[i] = 0.0;
        }
        for (std::size_t k = 0; k < MMsiz; ++k) {
            grad->dalpha[k] = 0.0;
            grad->dbeta[k] = 0.0;
        }
    }

    // Pass 1: event term. Decay to the event, read lambda, then excite, so an
    // event never excites another at the same timestamp (t^j_m < t).
    Real      event_term = 0.0;
    Real      t_prev     = 0.0;
    const bool want_grad = (grad != nullptr);

    // Simultaneous events form a group. Every event at one timestamp is
    // evaluated against the state before any of them excites, because
    // mathematics.md section 1 sums over t^j_m < t and not <= t. Exciting
    // inside the loop would let the second of two tied events see the first.
    Index k = 0;
    while (k < ev.n) {
        const Real t  = ev.times[k];
        const Real dt = t - t_prev;

        if (dt > 0.0) {
            for (Index i = 0; i < M; ++i) {
                const std::size_t base  = cell(i, 0, M);
                const Real*       b_row = be + base;
                for (Index j = 0; j < M; ++j) {
                    const Real e     = std::exp(-b_row[j] * dt);
                    const Real s_old = S_[base + static_cast<std::size_t>(j)];
                    U_[base + static_cast<std::size_t>(j)] =
                        e * (U_[base + static_cast<std::size_t>(j)] + dt * s_old);
                    S_[base + static_cast<std::size_t>(j)] = e * s_old;
                }
            }
        }

        Index group_end = k;
        while (group_end < ev.n && ev.times[group_end] == t) {
            ++group_end;
        }

        for (Index q = k; q < group_end; ++q) {
            const Index       d     = static_cast<Index>(ev.types[q]);
            const std::size_t dbase = cell(d, 0, M);

            Real lambda = mu[d];
            for (Index j = 0; j < M; ++j) {
                lambda += al[dbase + static_cast<std::size_t>(j)] *
                          S_[dbase + static_cast<std::size_t>(j)];
            }

            if (!(lambda > 0.0)) {
                if (grad != nullptr) {
                    for (Index i = 0; i < M; ++i) {
                        grad->dmu[i] = kNaN;
                    }
                    for (std::size_t c = 0; c < MMsiz; ++c) {
                        grad->dalpha[c] = kNaN;
                        grad->dbeta[c] = kNaN;
                    }
                }
                return kNegInf;
            }

            const Real inv = 1.0 / lambda;
            event_term += std::log(lambda);

            if (want_grad) {
                grad->dmu[d] += inv;
                for (Index j = 0; j < M; ++j) {
                    const std::size_t c = dbase + static_cast<std::size_t>(j);
                    grad->dalpha[c] += S_[c] * inv;
                    // d lambda_i / d beta_ij = -alpha_ij U_ij, and the event
                    // term contributes d lambda / lambda.
                    grad->dbeta[c] -= al[c] * U_[c] * inv;
                }
            }
        }

        for (Index q = k; q < group_end; ++q) {
            const Index d = static_cast<Index>(ev.types[q]);
            for (Index i = 0; i < M; ++i) {
                S_[cell(i, d, M)] += 1.0;
            }
        }

        t_prev = t;
        k      = group_end;
    }

    // Pass 2: compensator. mu_i T plus, per cell, (alpha/beta) C.
    Real compensator = 0.0;
    for (Index i = 0; i < M; ++i) {
        compensator += mu[i] * T;
    }

    // Cell (i, j) sums over events of type j only: the excitation a type-j
    // event injects into intensity i is what the compensator integrates.
    for (std::size_t c = 0; c < MMsiz; ++c) {
        C_[c] = 0.0;
        Q_[c] = 0.0;
    }
    for (Index m = 0; m < ev.n; ++m) {
        const Real        u = T - ev.times[m];
        const Index       j = static_cast<Index>(ev.types[m]);
        for (Index i = 0; i < M; ++i) {
            const std::size_t c = cell(i, j, M);
            const Real        x = be[c] * u;
            C_[c] += one_minus_decay(x);
            if (want_grad) {
                Q_[c] += one_minus_one_plus_x_decay(x);
            }
        }
    }

    for (std::size_t c = 0; c < MMsiz; ++c) {
        const Real beta = be[c];
        compensator += (al[c] / beta) * C_[c];
        if (want_grad) {
            grad->dalpha[c] -= C_[c] / beta;
            // -d/dbeta[(alpha/beta) C] = alpha Q / beta^2
            grad->dbeta[c] += al[c] * Q_[c] / (beta * beta);
        }
    }

    if (want_grad) {
        for (Index i = 0; i < M; ++i) {
            grad->dmu[i] -= T;
        }
    }

    return event_term - compensator;
}

// ---------------------------------------------------------------------------
// Shared decay, beta_ij = beta_j
// ---------------------------------------------------------------------------

SharedWorkspace::SharedWorkspace(Index M)
    : M_(M),
      S_(static_cast<std::size_t>(M), 0.0),
      U_(static_cast<std::size_t>(M), 0.0),
      C_(static_cast<std::size_t>(M), 0.0),
      Q_(static_cast<std::size_t>(M), 0.0) {}

Real SharedWorkspace::evaluate(const EventView& ev, const ParamView& p, Real T, Gradient* grad) {
    const Index M     = M_;
    const Real* mu    = p.mu;
    const Real* al    = p.alpha;
    const Real* be    = p.beta;

    for (Index j = 0; j < M; ++j) {
        S_[static_cast<std::size_t>(j)] = 0.0;
        U_[static_cast<std::size_t>(j)] = 0.0;
    }
    if (grad != nullptr) {
        for (Index i = 0; i < M; ++i) {
            grad->dmu[i] = 0.0;
        }
        for (Index i = 0; i < M; ++i) {
            for (Index j = 0; j < M; ++j) {
                grad->dalpha[cell(i, j, M)] = 0.0;
            }
            grad->dbeta[i] = 0.0;
        }
    }

    Real      event_term = 0.0;
    Real      t_prev     = 0.0;
    const bool want_grad = (grad != nullptr);

    // Simultaneous events form a group; see the pair evaluator. The tie rule is
    // a property of the model, not of the parameterization.
    Index k = 0;
    while (k < ev.n) {
        const Real t  = ev.times[k];
        const Real dt = t - t_prev;

        if (dt > 0.0) {
            for (Index j = 0; j < M; ++j) {
                const std::size_t kk = static_cast<std::size_t>(j);
                const Real        e  = std::exp(-be[j] * dt);
                const Real        s  = S_[kk];
                U_[kk]               = e * (U_[kk] + dt * s);
                S_[kk]               = e * s;
            }
        }

        Index group_end = k;
        while (group_end < ev.n && ev.times[group_end] == t) {
            ++group_end;
        }

        for (Index q = k; q < group_end; ++q) {
            const Index d = static_cast<Index>(ev.types[q]);

            Real lambda = mu[d];
            for (Index j = 0; j < M; ++j) {
                lambda += al[cell(d, j, M)] * S_[static_cast<std::size_t>(j)];
            }

            if (!(lambda > 0.0)) {
                if (grad != nullptr) {
                    for (Index i = 0; i < M; ++i) {
                        grad->dmu[i] = kNaN;
                        for (Index j = 0; j < M; ++j) {
                            grad->dalpha[cell(i, j, M)] = kNaN;
                        }
                        grad->dbeta[i] = kNaN;
                    }
                }
                return kNegInf;
            }

            const Real inv = 1.0 / lambda;
            event_term += std::log(lambda);

            if (want_grad) {
                grad->dmu[d] += inv;
                for (Index j = 0; j < M; ++j) {
                    const std::size_t c = cell(d, j, M);
                    grad->dalpha[c] += S_[static_cast<std::size_t>(j)] * inv;
                    // beta_j enters every target row, not just row d.
                    grad->dbeta[j] -= al[c] * U_[static_cast<std::size_t>(j)] * inv;
                }
            }
        }

        for (Index q = k; q < group_end; ++q) {
            S_[static_cast<std::size_t>(ev.types[q])] += 1.0;
        }

        t_prev = t;
        k      = group_end;
    }

    Real compensator = 0.0;
    for (Index i = 0; i < M; ++i) {
        compensator += mu[i] * T;
    }

    // C_j sums over events of type j, since beta_ij = beta_j is source-only.
    for (Index j = 0; j < M; ++j) {
        C_[static_cast<std::size_t>(j)] = 0.0;
        Q_[static_cast<std::size_t>(j)] = 0.0;
    }
    for (Index m = 0; m < ev.n; ++m) {
        const std::size_t kk = static_cast<std::size_t>(ev.types[m]);
        const Real        u  = T - ev.times[m];
        const Real        x  = be[kk] * u;
        C_[kk] += one_minus_decay(x);
        if (want_grad) {
            Q_[kk] += one_minus_one_plus_x_decay(x);
        }
    }

    for (Index i = 0; i < M; ++i) {
        for (Index j = 0; j < M; ++j) {
            const std::size_t c    = cell(i, j, M);
            const Real        beta = be[j];
            compensator += (al[c] / beta) * C_[static_cast<std::size_t>(j)];
            if (want_grad) {
                grad->dalpha[c] -= C_[static_cast<std::size_t>(j)] / beta;
                grad->dbeta[j] += al[c] * Q_[static_cast<std::size_t>(j)] / (beta * beta);
            }
        }
    }

    if (want_grad) {
        for (Index i = 0; i < M; ++i) {
            grad->dmu[i] -= T;
        }
    }

    return event_term - compensator;
}

}  // namespace hawkes
