// SPDX-License-Identifier: MIT

#include "hawkes/rng.hpp"

#include <cmath>

namespace hawkes {

namespace {

constexpr std::uint64_t kGolden = 0x9E3779B97F4A7C15ULL;

// PCG_DEFAULT_MULTIPLIER_128 of the reference implementation (O'Neill 2014).
constexpr std::uint64_t kMulHi = 0x2360ED051FC65DA4ULL;
constexpr std::uint64_t kMulLo = 0x4385DF649FCCF645ULL;

// High 64 bits of a 64x64 product, in portable integer arithmetic; MSVC has no
// unsigned __int128.
std::uint64_t mulhi(std::uint64_t a, std::uint64_t b) noexcept {
    const std::uint64_t a_lo = a & 0xFFFFFFFFULL, a_hi = a >> 32;
    const std::uint64_t b_lo = b & 0xFFFFFFFFULL, b_hi = b >> 32;
    const std::uint64_t p0 = a_lo * b_lo;
    const std::uint64_t p1 = a_lo * b_hi;
    const std::uint64_t p2 = a_hi * b_lo;
    const std::uint64_t p3 = a_hi * b_hi;
    const std::uint64_t mid = (p0 >> 32) + (p1 & 0xFFFFFFFFULL) + (p2 & 0xFFFFFFFFULL);
    return p3 + (p1 >> 32) + (p2 >> 32) + (mid >> 32);
}

std::uint64_t rotr(std::uint64_t x, unsigned r) noexcept {
    return (x >> r) | (x << ((64U - r) & 63U));
}

// log(k!) for k >= 0.
Real log_factorial(std::uint64_t k) noexcept {
    return std::lgamma(static_cast<Real>(k) + 1.0);
}

std::uint64_t poisson_inversion(Rng& rng, Real mean) noexcept {
    // Sequential search on the CDF. mean < 10 keeps exp(-mean) far from
    // underflow and the expected number of steps near mean + 1.
    const Real    p0 = std::exp(-mean);
    Real          u  = rng.uniform01();
    Real          p  = p0;
    std::uint64_t k  = 0;
    while (u > p) {
        u -= p;
        ++k;
        p *= mean / static_cast<Real>(k);
        // Rounding can leave u above the summed tail; the cap is far in the
        // tail (mean < 10) and ends the search with probability ~1e-30.
        if (k > 1000) {
            break;
        }
    }
    return k;
}

std::uint64_t poisson_ptrs(Rng& rng, Real mu) noexcept {
    const Real smu       = std::sqrt(mu);
    const Real b         = 0.931 + 2.53 * smu;
    const Real a         = -0.059 + 0.02483 * b;
    const Real inv_alpha = 1.1239 + 1.1328 / (b - 3.4);
    const Real vr        = 0.9277 - 3.6224 / (b - 2.0);
    const Real log_mu    = std::log(mu);
    const Real log_ia    = std::log(inv_alpha);
    for (;;) {
        const Real U  = rng.uniform01() - 0.5;
        const Real V  = rng.uniform01();
        const Real us = 0.5 - std::fabs(U);
        const Real kf = std::floor((2.0 * a / us + b) * U + mu + 0.43);
        if (us >= 0.07 && V <= vr) {
            return static_cast<std::uint64_t>(kf);
        }
        if (kf < 0.0 || (us < 0.013 && V > us)) {
            continue;
        }
        const auto k = static_cast<std::uint64_t>(kf);
        if (std::log(V) + log_ia - std::log(a / (us * us) + b) <=
            -mu + kf * log_mu - log_factorial(k)) {
            return k;
        }
    }
}

}  // namespace

std::uint64_t splitmix64(std::uint64_t& state) noexcept {
    state += kGolden;
    std::uint64_t z = state;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

std::uint64_t seed_stream(std::uint64_t seed, std::uint64_t index) noexcept {
    std::uint64_t s = seed;
    const std::uint64_t base = splitmix64(s);
    std::uint64_t t = base + kGolden * (index + 1);
    return splitmix64(t);
}

Rng::Rng(std::uint64_t seed) noexcept {
    std::uint64_t s = seed;
    init_.state_hi  = splitmix64(s);
    init_.state_lo  = splitmix64(s);
    init_.inc_hi    = splitmix64(s);
    init_.inc_lo    = splitmix64(s) | 1ULL;  // the increment must be odd
    state_hi_ = init_.state_hi;
    state_lo_ = init_.state_lo;
    inc_hi_   = init_.inc_hi;
    inc_lo_   = init_.inc_lo;
}

std::uint64_t Rng::next_u64() noexcept {
    // state = state * multiplier + inc  (mod 2^128), then output the new state.
    const std::uint64_t lo_hi = mulhi(state_lo_, kMulLo);
    const std::uint64_t lo    = state_lo_ * kMulLo;
    const std::uint64_t hi    = lo_hi + state_lo_ * kMulHi + state_hi_ * kMulLo;
    state_lo_ = lo + inc_lo_;
    state_hi_ = hi + inc_hi_ + (state_lo_ < lo ? 1U : 0U);
    // XSL-RR: fold the halves, rotate by the top six bits of the state.
    return rotr(state_hi_ ^ state_lo_, static_cast<unsigned>(state_hi_ >> 58));
}

Real Rng::uniform01() noexcept {
    const std::uint64_t k = next_u64() >> 12;
    return (static_cast<Real>(k) + 0.5) * 0x1.0p-52;
}

Real Rng::exponential(Real rate) noexcept {
    return -std::log1p(-uniform01()) / rate;
}

std::uint64_t Rng::poisson(Real mean) noexcept {
    if (mean <= 0.0) {
        return 0;
    }
    return mean < 10.0 ? poisson_inversion(*this, mean) : poisson_ptrs(*this, mean);
}

}  // namespace hawkes
