// SPDX-License-Identifier: MIT
//
// Random number generation, per ADR-005: SplitMix64 seeding a PCG64 (XSL-RR,
// 128-bit state) engine, with every distribution built here from raw 64-bit
// draws.
//
// Results are reproducible across platforms for the same seed. The integer
// stage (next_u64, uniform01) is bit-identical everywhere because it uses only
// integer arithmetic and one exact scaling. exponential() and poisson() add
// log/log1p/lgamma, which the C++ standard does not pin to the last bit, so
// their values can differ by an ulp between standard libraries; the golden
// tests state the tolerance. No standard-library distribution is used anywhere,
// since their output is implementation-defined.
//
// No global state: every generator is constructed from an explicit seed.

#pragma once

#include <cstdint>

#include "hawkes/types.hpp"

namespace hawkes {

// One step of SplitMix64 (Steele, Lea & Flood 2014). Advances `state` and
// returns the mixed output.
[[nodiscard]] std::uint64_t splitmix64(std::uint64_t& state) noexcept;

// Seed of the i-th independent stream derived from `seed`. For a fixed seed the
// map i -> seed_stream(seed, i) is injective: it adds an odd multiple of i to
// a fixed word and applies the SplitMix64 finaliser, both bijections of
// Z/2^64.
[[nodiscard]] std::uint64_t seed_stream(std::uint64_t seed, std::uint64_t index) noexcept;

class Rng {
public:
    explicit Rng(std::uint64_t seed) noexcept;

    [[nodiscard]] std::uint64_t next_u64() noexcept;

    // Uniform on the open interval (0, 1): (k + 1/2) * 2^-52 for a 52-bit k.
    // Never 0, so log(U) is finite, and never 1, so log1p(-U) is. 53 bits would
    // round the largest midpoint to exactly 1.0.
    [[nodiscard]] Real uniform01() noexcept;

    // Inverse transform, -log1p(-U) / rate. Strictly positive and finite for
    // rate > 0.
    [[nodiscard]] Real exponential(Real rate) noexcept;

    // Inversion by sequential search for mean < 10; the transformed rejection
    // with squeeze PTRS of Hormann (1993) above. mean >= 0 and finite.
    [[nodiscard]] std::uint64_t poisson(Real mean) noexcept;

    // Initial state and increment, exposed so the engine can be checked against
    // an independent PCG64 implementation.
    struct Words {
        std::uint64_t state_hi, state_lo, inc_hi, inc_lo;
    };
    [[nodiscard]] Words initial_words() const noexcept { return init_; }

private:
    std::uint64_t state_hi_, state_lo_;
    std::uint64_t inc_hi_, inc_lo_;
    Words         init_;
};

}  // namespace hawkes
