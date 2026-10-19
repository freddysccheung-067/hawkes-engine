// SPDX-License-Identifier: MIT
//
// Contract tests for the likelihood core. The numerical agreement with the
// reference implementation is established in tests/test_oracle_agreement.py;
// these pin the closed-form cases that a value comparison alone would not catch,
// and the error behaviour the headers promise.

#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "hawkes/loglik.hpp"
#include "hawkes/types.hpp"
#include "hawkes/validation.hpp"

using namespace hawkes;
using Catch::Approx;

namespace {

struct Case {
    std::vector<Real>        times;
    std::vector<std::uint8_t> types;
    std::vector<Real>        mu;
    std::vector<Real>        alpha;
    std::vector<Real>        beta;
    Real                     T;

    [[nodiscard]] EventView events() const {
        return EventView{times.data(), types.data(), static_cast<Index>(times.size())};
    }
    [[nodiscard]] ParamView params() const {
        return ParamView{static_cast<Index>(mu.size()), mu.data(), alpha.data(), beta.data()};
    }
};

}  // namespace

TEST_CASE("zero events is minus the baseline compensator", "[loglik]") {
    Case c{{}, {}, {0.5, 1.25, 2.0}, std::vector<Real>(9, 0.0), std::vector<Real>(9, 1.0), 4.0};

    std::vector<Real> dmu(3);
    std::vector<Real> da(9);
    std::vector<Real> db(9);
    Gradient          g{dmu.data(), da.data(), db.data()};

    const Real value = loglik(c.events(), c.params(), c.T, &g);
    CHECK(value == Approx(-(0.5 + 1.25 + 2.0) * 4.0));

    for (Index i = 0; i < 3; ++i) {
        CHECK(dmu[static_cast<std::size_t>(i)] == Approx(-4.0));
    }
    for (std::size_t k = 0; k < 9; ++k) {
        CHECK(da[k] == 0.0);
        CHECK(db[k] == 0.0);
    }
}

TEST_CASE("a single event sees the bare baseline", "[loglik]") {
    Case c{{2.0}, {0}, {0.7}, {0.3}, {1.5}, 6.0};

    const Real decay = std::exp(-1.5 * 4.0);
    const Real expected =
        std::log(0.7) - 0.7 * 6.0 - (0.3 / 1.5) * (-std::expm1(-1.5 * 4.0));

    std::vector<Real> dmu(1);
    std::vector<Real> da(1);
    std::vector<Real> db(1);
    Gradient          g{dmu.data(), da.data(), db.data()};
    const Real        value = loglik(c.events(), c.params(), c.T, &g);

    CHECK(value == Approx(expected).epsilon(1e-14));
    CHECK(dmu[0] == Approx(1.0 / 0.7 - 6.0));
    CHECK(da[0] == Approx(-(-std::expm1(-1.5 * 4.0)) / 1.5).epsilon(1e-14));

    // d/dbeta of [log mu - mu T - (alpha/beta)(1 - exp(-beta u))], u = T - t.
    const Real u = 4.0;
    const Real dbeta = 0.3 * (1.0 - (1.0 + 1.5 * u) * decay) / (1.5 * 1.5);
    CHECK(db[0] == Approx(dbeta).epsilon(1e-14));
}

TEST_CASE("simultaneous events do not excite each other", "[loglik]") {
    // mathematics.md section 1 sums over t^j_m < t. Two events at t = 1 must
    // both see the baseline, and both must be visible from t = 2.
    Case c{{1.0, 1.0, 2.0}, {0, 0, 0}, {0.5}, {0.2}, {1.0}, 5.0};

    const Real at_two = 0.5 + 0.2 * 2.0 * std::exp(-1.0);
    const Real compensator =
        0.5 * 5.0 + (0.2 / 1.0) *
                        (2.0 * (-std::expm1(-1.0 * 4.0)) + (-std::expm1(-1.0 * 3.0)));
    const Real expected = 2.0 * std::log(0.5) + std::log(at_two) - compensator;

    CHECK(loglik(c.events(), c.params(), c.T) == Approx(expected).epsilon(1e-14));
}

TEST_CASE("non-positive intensity returns minus infinity and a NaN gradient", "[loglik]") {
    Case c{{1.0}, {0}, {0.0}, {0.0}, {1.0}, 5.0};

    std::vector<Real> dmu(1);
    std::vector<Real> da(1);
    std::vector<Real> db(1);
    Gradient          g{dmu.data(), da.data(), db.data()};

    const Real value = loglik(c.events(), c.params(), c.T, &g);
    CHECK(value == -std::numeric_limits<Real>::infinity());
    CHECK(std::isnan(dmu[0]));
    CHECK(std::isnan(da[0]));
    CHECK(std::isnan(db[0]));

    // A value is never NaN: -inf means "undefined here", NaN would mean a bug.
    CHECK(!std::isnan(value));
}

TEST_CASE("shared decay reproduces the pair result when beta is broadcast", "[loglik]") {
    Case pair{{0.4, 1.1, 1.9, 3.0}, {0, 1, 0, 1}, {0.6, 0.9},
              {0.1, 0.35, 0.2, 0.05}, {1.3, 1.7, 1.3, 1.7}, 6.0};
    // Row i of the pair block is the shared vector, per target.
    Case shared{pair.times, pair.types, pair.mu, pair.alpha, {1.3, 1.7}, pair.T};

    const Real pair_value   = loglik(pair.events(), pair.params(), pair.T);
    const Real shared_value = loglik_shared(shared.events(), shared.params(), shared.T);
    CHECK(shared_value == Approx(pair_value).epsilon(1e-15));

    std::vector<Real> pmu(2), pa(4), pb(4);
    Gradient          pg{pmu.data(), pa.data(), pb.data()};
    (void)loglik(pair.events(), pair.params(), pair.T, &pg);

    std::vector<Real> smu(2), sa(4), sb(2);
    Gradient          sg{smu.data(), sa.data(), sb.data()};
    (void)loglik_shared(shared.events(), shared.params(), shared.T, &sg);

    for (Index i = 0; i < 2; ++i) {
        CHECK(smu[static_cast<std::size_t>(i)] == Approx(pmu[static_cast<std::size_t>(i)]));
    }
    for (std::size_t k = 0; k < 4; ++k) {
        CHECK(sa[k] == Approx(pa[k]));
    }
    // dbeta_j totals the row contributions from every target.
    for (Index j = 0; j < 2; ++j) {
        const Real col = pb[static_cast<std::size_t>(j)] +
                         pb[static_cast<std::size_t>(2) + static_cast<std::size_t>(j)];
        CHECK(sb[static_cast<std::size_t>(j)] == Approx(col));
    }
}

TEST_CASE("log-space gradient scales each entry by its own parameter", "[loglik]") {
    Case c{{0.5, 1.5}, {0, 0}, {0.8, 1.1}, {0.2, 0.4, 0.1, 0.3}, {1.2, 1.9, 1.4, 1.1}, 3.0};

    std::vector<Real> mu(2), a(4), b(4);
    Gradient          g{mu.data(), a.data(), b.data()};
    (void)loglik(c.events(), c.params(), c.T, &g);
    const std::vector<Real> natural_mu = mu;
    const std::vector<Real> natural_a = a;
    const std::vector<Real> natural_b = b;

    log_space_gradient(c.params(), g);
    for (Index i = 0; i < 2; ++i) {
        CHECK(mu[static_cast<std::size_t>(i)] ==
              Approx(natural_mu[static_cast<std::size_t>(i)] * c.mu[static_cast<std::size_t>(i)]));
    }
    for (std::size_t k = 0; k < 4; ++k) {
        CHECK(a[k] == Approx(natural_a[k] * c.alpha[k]));
        CHECK(b[k] == Approx(natural_b[k] * c.beta[k]));
    }
}

TEST_CASE("validation names the offending entry", "[validation]") {
    Case bad{{1.0, 0.5}, {0, 0}, {1.0}, {0.1}, {1.0}, 2.0};
    CHECK_THROWS_AS(validate_events(bad.events(), 1), std::invalid_argument);

    Case bad_type{{1.0}, {3}, {1.0}, {0.1}, {1.0}, 2.0};
    CHECK_THROWS_AS(validate_events(bad_type.events(), 1), std::invalid_argument);

    Case bad_beta{{1.0}, {0}, {1.0}, {0.1}, {0.0}, 2.0};
    CHECK_THROWS_AS(validate_params(bad_beta.params()), std::invalid_argument);

    Case bad_mu{{1.0}, {0}, {-1.0}, {0.1}, {1.0}, 2.0};
    CHECK_THROWS_AS(validate_params(bad_mu.params()), std::invalid_argument);

    Case nan_mu{{1.0}, {0}, {std::numeric_limits<Real>::quiet_NaN()}, {0.1}, {1.0}, 2.0};
    CHECK_THROWS_AS(validate_params(nan_mu.params()), std::invalid_argument);
}
