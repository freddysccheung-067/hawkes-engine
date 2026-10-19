// SPDX-License-Identifier: MIT
//
// Contract tests for the simulators and the diagnostics. The statistical
// agreement between the two simulators is tested in Python, where scipy is
// available; here are the properties that must hold for every seed.

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_string.hpp>

#include "hawkes/diagnostics.hpp"
#include "hawkes/simulate_cluster.hpp"
#include "hawkes/simulate_thin.hpp"

using namespace hawkes;
using Catch::Matchers::ContainsSubstring;

namespace {

struct Model {
    std::vector<Real> mu{0.5, 0.3};
    std::vector<Real> alpha{0.20, 0.10, 0.15, 0.25};
    std::vector<Real> beta{1.0, 1.2, 1.1, 1.3};
    ParamView view() const { return ParamView{2, mu.data(), alpha.data(), beta.data()}; }
};

using Simulator = EventStream (*)(const ParamView&, Real, std::uint64_t, Real, Real);

EventStream thin(const ParamView& p, Real T, std::uint64_t s, Real t0, Real b) {
    return simulate_thin(p, T, s, t0, b);
}
EventStream cluster(const ParamView& p, Real T, std::uint64_t s, Real t0, Real b) {
    return simulate_cluster(p, T, s, t0, b);
}

}  // namespace

TEST_CASE("spectral radius of a known matrix", "[sim]") {
    // alpha/beta = [[0.5, 0.25], [0.25, 0.5]] has eigenvalues 0.75 and 0.25.
    const std::vector<Real> mu{1.0, 1.0}, alpha{0.5, 0.25, 0.25, 0.5}, beta{1.0, 1.0, 1.0, 1.0};
    const ParamView p{2, mu.data(), alpha.data(), beta.data()};
    REQUIRE(std::fabs(spectral_radius(p) - 0.75) < 1e-12);
}

TEST_CASE("spectral radius converges on a periodic matrix", "[sim]") {
    // A permutation has eigenvalues of modulus 1 at several angles; plain power
    // iteration never settles on it.
    const std::vector<Real> mu{1.0, 1.0}, alpha{0.0, 0.9, 0.9, 0.0}, beta{1.0, 1.0, 1.0, 1.0};
    const ParamView p{2, mu.data(), alpha.data(), beta.data()};
    REQUIRE(std::fabs(spectral_radius(p) - 0.9) < 1e-12);
}

TEST_CASE("stationary mean solves (I - Gamma) m = mu", "[sim]") {
    Model m;
    const auto mean = stationary_mean(m.view());
    for (int i = 0; i < 2; ++i) {
        Real lhs = mean[static_cast<std::size_t>(i)];
        for (int j = 0; j < 2; ++j) {
            lhs -= m.alpha[static_cast<std::size_t>(2 * i + j)] /
                   m.beta[static_cast<std::size_t>(2 * i + j)] * mean[static_cast<std::size_t>(j)];
        }
        REQUIRE(std::fabs(lhs - m.mu[static_cast<std::size_t>(i)]) < 1e-14);
    }
}

TEST_CASE("both simulators honour the output contract", "[sim]") {
    Model m;
    for (Simulator run : {Simulator(thin), Simulator(cluster)}) {
        const auto a = run(m.view(), 200.0, 9, 0.0, 0.0);
        const auto b = run(m.view(), 200.0, 9, 0.0, 0.0);
        REQUIRE(a.first == b.first);
        REQUIRE(a.second == b.second);
        REQUIRE(a.first.size() == a.second.size());
        REQUIRE(a.first.size() > 100);
        REQUIRE(std::is_sorted(a.first.begin(), a.first.end()));
        REQUIRE(a.first.front() >= 0.0);
        REQUIRE(a.first.back() < 200.0);
        REQUIRE(*std::max_element(a.second.begin(), a.second.end()) < 2);
        REQUIRE(run(m.view(), 200.0, 10, 0.0, 0.0).first != a.first);
    }
}

TEST_CASE("a negative t0 shifts the window", "[sim]") {
    Model m;
    for (Simulator run : {Simulator(thin), Simulator(cluster)}) {
        const auto s = run(m.view(), 50.0, 3, -20.0, 5.0);
        REQUIRE(!s.first.empty());
        REQUIRE(s.first.front() >= -20.0);
        REQUIRE(s.first.back() < 50.0);
    }
}

TEST_CASE("rho >= 1 throws domain_error naming the radius", "[sim]") {
    const std::vector<Real> mu{0.5}, alpha{1.5}, beta{1.0};
    const ParamView p{1, mu.data(), alpha.data(), beta.data()};
    REQUIRE_THROWS_AS(simulate_thin(p, 10.0, 1), std::domain_error);
    REQUIRE_THROWS_AS(simulate_cluster(p, 10.0, 1), std::domain_error);
    REQUIRE_THROWS_WITH(simulate_thin(p, 10.0, 1), ContainsSubstring("1.5"));
    REQUIRE_THROWS_WITH(simulate_cluster(p, 10.0, 1), ContainsSubstring("1.5"));
}

TEST_CASE("malformed windows throw invalid_argument", "[sim]") {
    Model m;
    REQUIRE_THROWS_AS(simulate_thin(m.view(), 0.0, 1), std::invalid_argument);
    REQUIRE_THROWS_AS(simulate_cluster(m.view(), -1.0, 1), std::invalid_argument);
    REQUIRE_THROWS_AS(simulate_thin(m.view(), 10.0, 1, 10.0), std::invalid_argument);
    REQUIRE_THROWS_AS(simulate_cluster(m.view(), 10.0, 1, 0.0, -1.0), std::invalid_argument);
}

TEST_CASE("zero parameters give an empty stream", "[sim]") {
    const std::vector<Real> mu{0.0, 0.0}, alpha{0.0, 0.0, 0.0, 0.0}, beta{1.0, 1.0, 1.0, 1.0};
    const ParamView p{2, mu.data(), alpha.data(), beta.data()};
    REQUIRE(simulate_thin(p, 10.0, 1).first.empty());
    REQUIRE(simulate_cluster(p, 10.0, 1).second.empty());
}

TEST_CASE("the cluster node limit throws and names rho", "[sim]") {
    Model m;
    REQUIRE_THROWS_AS(simulate_cluster(m.view(), 1000.0, 1, 0.0, 0.0, 10), std::runtime_error);
    REQUIRE_THROWS_WITH(simulate_cluster(m.view(), 1000.0, 1, 0.0, 0.0, 10),
                        ContainsSubstring("rho"));
}

TEST_CASE("rescaling a stream under its own model gives unit-mean gaps", "[sim]") {
    Model m;
    const auto s = simulate_thin(m.view(), 4000.0, 21);
    const EventView ev{s.first.data(), s.second.data(), static_cast<Index>(s.first.size())};
    const auto gaps = time_rescale(ev, m.view());
    REQUIRE(gaps.size() == 2);
    for (const auto& g : gaps) {
        REQUIRE(g.size() > 500);
        Real sum = 0.0;
        for (Real x : g) {
            REQUIRE(x > 0.0);
            sum += x;
        }
        REQUIRE(std::fabs(sum / static_cast<Real>(g.size()) - 1.0) < 5.0 / std::sqrt(static_cast<Real>(g.size())));
    }
}

TEST_CASE("rescaled gaps of a single dimension sum to the compensator", "[sim]") {
    // M = 1, no excitation: gap k is mu * (t_k - t_{k-1}) exactly.
    const std::vector<Real> mu{2.0}, alpha{0.0}, beta{1.0};
    const ParamView p{1, mu.data(), alpha.data(), beta.data()};
    const std::vector<Real> t{0.5, 1.0, 3.0};
    const std::vector<std::uint8_t> k{0, 0, 0};
    const auto gaps = time_rescale(EventView{t.data(), k.data(), 3}, p);
    REQUIRE(gaps[0].size() == 3);
    REQUIRE(std::fabs(gaps[0][0] - 1.0) < 1e-15);
    REQUIRE(std::fabs(gaps[0][1] - 1.0) < 1e-15);
    REQUIRE(std::fabs(gaps[0][2] - 4.0) < 1e-15);
}
