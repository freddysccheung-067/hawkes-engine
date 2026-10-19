// SPDX-License-Identifier: MIT

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "hawkes/rng.hpp"

using namespace hawkes;

namespace {

// Regularized lower incomplete gamma P(a, x): series for x < a + 1, continued
// fraction otherwise. Enough to turn a chi-square statistic into a p-value.
double gamma_p(double a, double x) {
    if (x <= 0.0) {
        return 0.0;
    }
    const double gln = std::lgamma(a);
    if (x < a + 1.0) {
        double ap = a, sum = 1.0 / a, del = sum;
        for (int n = 0; n < 2000; ++n) {
            ap += 1.0;
            del *= x / ap;
            sum += del;
            if (std::fabs(del) < std::fabs(sum) * 1e-16) {
                break;
            }
        }
        return sum * std::exp(-x + a * std::log(x) - gln);
    }
    double b = x + 1.0 - a, c = 1e300, d = 1.0 / b, h = d;
    for (int i = 1; i < 2000; ++i) {
        const double an = -i * (i - a);
        b += 2.0;
        d = an * d + b;
        if (std::fabs(d) < 1e-300) d = 1e-300;
        c = b + an / c;
        if (std::fabs(c) < 1e-300) c = 1e-300;
        d = 1.0 / d;
        const double del = d * c;
        h *= del;
        if (std::fabs(del - 1.0) < 1e-16) {
            break;
        }
    }
    return 1.0 - std::exp(-x + a * std::log(x) - gln) * h;
}

// Asymptotic Kolmogorov survival function with the Stephens small-sample
// correction.
double ks_pvalue(double d, std::size_t n) {
    const double sn = std::sqrt(static_cast<double>(n));
    const double lambda = (sn + 0.12 + 0.11 / sn) * d;
    double sum = 0.0;
    for (int k = 1; k <= 100; ++k) {
        sum += ((k % 2) ? 2.0 : -2.0) * std::exp(-2.0 * k * k * lambda * lambda);
    }
    return std::clamp(sum, 0.0, 1.0);
}

std::vector<std::vector<std::string>> load_golden() {
    std::ifstream in(HAWKES_GOLDEN_DIR "/rng.txt");
    REQUIRE(in.good());
    std::vector<std::vector<std::string>> rows;
    std::string line;
    while (std::getline(in, line)) {
        std::istringstream ss(line);
        std::vector<std::string> tok;
        for (std::string w; ss >> w;) {
            tok.push_back(w);
        }
        rows.push_back(tok);
    }
    return rows;
}

}  // namespace

TEST_CASE("same seed gives the same stream", "[rng]") {
    Rng a(123), b(123), c(124);
    bool differs = false;
    for (int i = 0; i < 100; ++i) {
        const auto x = a.next_u64();
        REQUIRE(x == b.next_u64());
        differs = differs || x != c.next_u64();
    }
    REQUIRE(differs);
}

TEST_CASE("golden values", "[rng]") {
    const auto rows = load_golden();
    REQUIRE(rows.size() > 20);
    for (const auto& row : rows) {
        const std::string& kind = row[0];
        const std::uint64_t seed = std::stoull(row[1]);
        if (kind == "words") {
            const auto w = Rng(seed).initial_words();
            REQUIRE(w.state_hi == std::stoull(row[2], nullptr, 16));
            REQUIRE(w.state_lo == std::stoull(row[3], nullptr, 16));
            REQUIRE(w.inc_hi == std::stoull(row[4], nullptr, 16));
            REQUIRE(w.inc_lo == std::stoull(row[5], nullptr, 16));
        } else if (kind == "u64") {
            Rng r(seed);
            for (std::size_t i = 2; i < row.size(); ++i) {
                REQUIRE(r.next_u64() == std::stoull(row[i]));
            }
        } else if (kind == "uniform") {
            // Integer draw times an exact power of two: bit-identical.
            Rng r(seed);
            for (std::size_t i = 2; i < row.size(); ++i) {
                REQUIRE(r.uniform01() == std::stod(row[i]));
            }
        } else if (kind == "exp") {
            // log1p is not pinned to the last bit by the standard.
            Rng r(seed);
            for (std::size_t i = 2; i < row.size(); ++i) {
                const double want = std::stod(row[i]);
                REQUIRE(std::fabs(r.exponential(2.5) - want) <= 1e-14 * want);
            }
        } else if (kind == "poisson") {
            Rng r(seed);
            const double mean = std::stod(row[2]);
            for (std::size_t i = 3; i < row.size(); ++i) {
                REQUIRE(r.poisson(mean) == std::stoull(row[i]));
            }
        } else if (kind == "stream") {
            for (std::size_t i = 0; i + 2 < row.size(); ++i) {
                REQUIRE(seed_stream(seed, i) == std::stoull(row[i + 2]));
            }
        }
    }
}

TEST_CASE("seed streams are distinct", "[rng]") {
    std::set<std::uint64_t> seeds;
    for (std::uint64_t i = 0; i < 1000; ++i) {
        seeds.insert(seed_stream(99, i));
    }
    REQUIRE(seeds.size() == 1000);
    REQUIRE(seed_stream(99, 0) != seed_stream(100, 0));
}

TEST_CASE("uniform01 is in the open unit interval", "[rng]") {
    Rng r(5);
    for (int i = 0; i < 1000000; ++i) {
        const double u = r.uniform01();
        REQUIRE(u > 0.0);
        REQUIRE(u < 1.0);
    }
}

TEST_CASE("uniform01 passes chi-square uniformity", "[rng]") {
    constexpr int kBins = 100;
    constexpr int kN    = 1000000;
    Rng r(2024);
    std::vector<int> count(kBins, 0);
    for (int i = 0; i < kN; ++i) {
        ++count[static_cast<std::size_t>(r.uniform01() * kBins)];
    }
    double chi = 0.0;
    const double e = static_cast<double>(kN) / kBins;
    for (int c : count) {
        chi += (c - e) * (c - e) / e;
    }
    const double p = 1.0 - gamma_p((kBins - 1) / 2.0, chi / 2.0);
    INFO("chi2 = " << chi << ", p = " << p);
    REQUIRE(p > 1e-3);
}

TEST_CASE("exponential moments and KS against the exact CDF", "[rng]") {
    constexpr int kN = 200000;
    const double rate = 2.5;
    Rng r(77);
    std::vector<double> x(kN);
    double sum = 0.0, sq = 0.0;
    for (auto& v : x) {
        v = r.exponential(rate);
        REQUIRE(v > 0.0);
        sum += v;
        sq += v * v;
    }
    const double mean = sum / kN, var = sq / kN - mean * mean;
    REQUIRE(std::fabs(mean - 1.0 / rate) < 4.0 / rate / std::sqrt(static_cast<double>(kN)));
    // Var of the sample variance of Exp(1) is 8/n.
    REQUIRE(std::fabs(var - 1.0 / (rate * rate)) <
            4.0 * std::sqrt(8.0 / kN) / (rate * rate));
    std::sort(x.begin(), x.end());
    double d = 0.0;
    for (int i = 0; i < kN; ++i) {
        const double F = 1.0 - std::exp(-rate * x[static_cast<std::size_t>(i)]);
        d = std::max({d, F - static_cast<double>(i) / kN, static_cast<double>(i + 1) / kN - F});
    }
    const double p = ks_pvalue(d, kN);
    INFO("D = " << d << ", p = " << p);
    REQUIRE(p > 1e-3);
}

TEST_CASE("poisson mean and variance across regimes", "[rng]") {
    constexpr int kN = 200000;
    std::uint64_t seed = 31;
    for (double lam : {0.1, 1.0, 9.9, 10.0, 100.0, 1e4}) {
        Rng r(seed++);
        double sum = 0.0, sq = 0.0;
        for (int i = 0; i < kN; ++i) {
            const double k = static_cast<double>(r.poisson(lam));
            sum += k;
            sq += k * k;
        }
        const double mean = sum / kN, var = sq / kN - mean * mean;
        INFO("lambda = " << lam << " mean = " << mean << " var = " << var);
        REQUIRE(std::fabs(mean - lam) < 4.0 * std::sqrt(lam / kN));
        // Var of the sample variance of a Poisson is (mu4 - var^2) / n with
        // mu4 = lam + 3 lam^2, i.e. (lam + 2 lam^2) / n.
        REQUIRE(std::fabs(var - lam) < 4.0 * std::sqrt((lam + 2.0 * lam * lam) / kN));
    }
}

TEST_CASE("poisson matches the exact pmf", "[rng]") {
    constexpr int kN = 400000;
    for (double lam : {3.0, 10.0, 25.0}) {
        Rng r(static_cast<std::uint64_t>(lam * 1000));
        const int top = static_cast<int>(lam + 8.0 * std::sqrt(lam)) + 1;
        std::vector<double> obs(static_cast<std::size_t>(top) + 1, 0.0);
        for (int i = 0; i < kN; ++i) {
            obs[std::min<std::uint64_t>(r.poisson(lam), static_cast<std::uint64_t>(top))] += 1.0;
        }
        // Cells are k = 0..top-1 plus one tail cell, so every observation is
        // counted and the statistic has (cells - 1) degrees of freedom. Cells
        // with expected count below 5 are merged into the tail.
        double chi = 0.0, mass = 0.0, tail_obs = obs[static_cast<std::size_t>(top)];
        int cells = 0;
        for (int k = 0; k < top; ++k) {
            const double p = std::exp(-lam + k * std::log(lam) - std::lgamma(k + 1.0));
            const double e = kN * p;
            if (e < 5.0) {
                tail_obs += obs[static_cast<std::size_t>(k)];
                continue;
            }
            mass += p;
            chi += (obs[static_cast<std::size_t>(k)] - e) * (obs[static_cast<std::size_t>(k)] - e) / e;
            ++cells;
        }
        const double e_tail = kN * (1.0 - mass);
        chi += (tail_obs - e_tail) * (tail_obs - e_tail) / e_tail;
        ++cells;
        const double p = 1.0 - gamma_p((cells - 1) / 2.0, chi / 2.0);
        INFO("lambda = " << lam << " chi2 = " << chi << " cells = " << cells << " p = " << p);
        REQUIRE(p > 1e-3);
    }
}
