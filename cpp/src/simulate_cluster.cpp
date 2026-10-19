// SPDX-License-Identifier: MIT

#include "hawkes/simulate_cluster.hpp"

#include <algorithm>
#include <cstddef>
#include <sstream>
#include <stdexcept>

#include "hawkes/diagnostics.hpp"
#include "hawkes/rng.hpp"
#include "hawkes/validation.hpp"

namespace hawkes {

namespace {

struct Node {
    Real         t;
    std::uint8_t type;
};

}  // namespace

EventStream simulate_cluster(const ParamView& p, Real T, std::uint64_t seed, Real t0, Real burn_in,
                             std::uint64_t max_nodes) {
    validate_simulation(p, T, t0, burn_in);

    const auto M = static_cast<std::size_t>(p.M);
    Rng rng(seed);
    const Real start = t0 - burn_in;

    // The node list is its own breadth-first queue: the head index walks it
    // while children are appended, so no separate queue is allocated.
    std::vector<Node> nodes;
    auto push = [&](Real t, std::size_t type) {
        if (nodes.size() >= max_nodes) {
            std::ostringstream os;
            os.precision(17);
            os << "branching forest exceeded " << max_nodes << " events; rho(alpha/beta) = "
               << spectral_radius(p) << " is too close to 1 for this window";
            throw std::runtime_error(os.str());
        }
        nodes.push_back(Node{t, static_cast<std::uint8_t>(type)});
    };

    for (std::size_t i = 0; i < M; ++i) {
        const std::uint64_t n = rng.poisson(p.mu[i] * (T - start));
        for (std::uint64_t k = 0; k < n; ++k) {
            push(start + (T - start) * rng.uniform01(), i);
        }
    }

    for (std::size_t head = 0; head < nodes.size(); ++head) {
        const Node parent = nodes[head];
        for (std::size_t target = 0; target < M; ++target) {
            const std::size_t cell = target * M + parent.type;
            const std::uint64_t n = rng.poisson(p.alpha[cell] / p.beta[cell]);
            for (std::uint64_t k = 0; k < n; ++k) {
                const Real t = parent.t + rng.exponential(p.beta[cell]);
                if (t < T) {
                    push(t, target);
                }
            }
        }
    }

    // Stable, so events at exactly equal times keep generation order and the
    // output depends only on the seed.
    std::stable_sort(nodes.begin(), nodes.end(),
                     [](const Node& a, const Node& b) { return a.t < b.t; });
    EventStream out;
    for (const Node& n : nodes) {
        if (n.t >= t0) {
            out.first.push_back(n.t);
            out.second.push_back(n.type);
        }
    }
    return out;
}

}  // namespace hawkes
