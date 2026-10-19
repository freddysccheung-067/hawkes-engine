// SPDX-License-Identifier: MIT
//
// Proves the headline claim in workspace.hpp: the event loop allocates nothing.
//
// The global operator new is replaced for this test binary. A flag is raised
// around evaluate(); if any allocation reaches the replaced operator while it is
// raised, the test records the size and fails. The workspace is constructed
// before the flag goes up, so its buffers are not counted, and the gradient
// outputs are caller-owned vectors for the same reason.

#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <new>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "hawkes/types.hpp"
#include "hawkes/workspace.hpp"

namespace {

bool     g_watching = false;
unsigned g_allocations = 0;
std::size_t g_last_size = 0;

void note_alloc(std::size_t size) noexcept {
    if (g_watching) {
        ++g_allocations;
        g_last_size = size;
    }
}

}  // namespace

void* operator new(std::size_t size) {
    note_alloc(size);
    void* p = std::malloc(size == 0 ? 1 : size);
    if (p == nullptr) {
        throw std::bad_alloc();
    }
    return p;
}

void* operator new[](std::size_t size) {
    note_alloc(size);
    void* p = std::malloc(size == 0 ? 1 : size);
    if (p == nullptr) {
        throw std::bad_alloc();
    }
    return p;
}

// libstdc++ draws temporary buffers (std::stable_sort) from the nothrow form. If
// it were left to the default, the sanitizer would see memory from its own
// operator new released through the replaced delete below, which calls free.
void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
    note_alloc(size);
    return std::malloc(size == 0 ? 1 : size);
}

void* operator new[](std::size_t size, const std::nothrow_t&) noexcept {
    note_alloc(size);
    return std::malloc(size == 0 ? 1 : size);
}

void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

using namespace hawkes;

TEST_CASE("evaluate allocates nothing in the event loop", "[allocation]") {
    constexpr Index M = 4;
    constexpr Index N = 200;

    std::vector<Real> times(static_cast<std::size_t>(N));
    std::vector<std::uint8_t> types(static_cast<std::size_t>(N));
    for (Index k = 0; k < N; ++k) {
        times[static_cast<std::size_t>(k)] =
            0.01 * static_cast<Real>(k) + 0.001 * static_cast<Real>(k % 7);
        types[static_cast<std::size_t>(k)] = static_cast<std::uint8_t>(k % M);
    }
    std::vector<Real> mu(M, 0.5);
    std::vector<Real> alpha(static_cast<std::size_t>(M) * M, 0.05);
    std::vector<Real> beta(static_cast<std::size_t>(M) * M, 1.0);
    std::vector<Real> beta_shared(M, 1.0);

    EventView events{times.data(), types.data(), N};
    ParamView params{M, mu.data(), alpha.data(), beta.data()};
    ParamView params_shared{M, mu.data(), alpha.data(), beta_shared.data()};

    std::vector<Real> dmu(M, 0.0);
    std::vector<Real> dalpha(static_cast<std::size_t>(M) * M, 0.0);
    std::vector<Real> dbeta(static_cast<std::size_t>(M) * M, 0.0);
    std::vector<Real> dbeta_shared(M, 0.0);
    Gradient grad{dmu.data(), dalpha.data(), dbeta.data()};
    Gradient grad_shared{dmu.data(), dalpha.data(), dbeta_shared.data()};

    // Constructed before the flag goes up: buffer allocation is expected here.
    PairWorkspace   pair_ws(M);
    SharedWorkspace shared_ws(M);

    const Real T = 1.0 + 0.01 * static_cast<Real>(N);

    g_allocations = 0;
    g_last_size   = 0;
    g_watching    = true;

    const Real value_pair   = pair_ws.evaluate(events, params, T, &grad);
    const Real value_shared = shared_ws.evaluate(events, params_shared, T, &grad_shared);
    const Real value_nograd = pair_ws.evaluate(events, params, T, nullptr);

    g_watching = false;

    CHECK(g_allocations == 0);
    INFO("first allocation was " << g_last_size << " bytes");
    CHECK(value_pair == value_nograd);
    CHECK(std::isfinite(value_shared));
    CHECK(std::isfinite(value_pair));
}
