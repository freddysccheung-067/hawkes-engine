"""The flat free-parameter layout.

The optimizer, the Hessian and the trust report all need the same answer to
"which entries of (mu, alpha, beta) are estimated, and in what order". They get
it from one object, so a coordinate index means the same thing in a gradient, a
covariance row and a diagnostic message.

Order is ``mu``, then ``alpha`` row-major, then ``beta`` row-major (or by source
when the decay is shared), matching the C++ gradient layout fixed by ADR-002.

A non-free entry is a constant, not a parameter: it holds a supplied value, is
written into every array handed to the core, and never appears in the flat
vector. That is why ``zero_diagonal`` masks rather than projects — a projected
coordinate is still a coordinate, and the optimizer would keep stepping along a
direction the model does not have. The same reasoning makes a fixed block
disappear from the vector entirely rather than being pinned at its value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np

from hawkes_engine._typing import BoolArray, FloatArray, IndexArray


@dataclass(frozen=True)
class Layout:
    """Which entries of the parameter block are free, and what the rest hold."""

    M: int
    shared_decay: bool = False
    zero_diagonal: bool = False
    free_mu: bool = True
    free_alpha: bool = True
    free_beta: bool = True
    mu_const: FloatArray | None = field(default=None, repr=False)
    alpha_const: FloatArray | None = field(default=None, repr=False)
    beta_const: FloatArray | None = field(default=None, repr=False)

    @cached_property
    def beta_shape(self) -> tuple[int, ...]:
        return (self.M,) if self.shared_decay else (self.M, self.M)

    @cached_property
    def mu_free(self) -> BoolArray:
        return np.full(self.M, self.free_mu, dtype=bool)

    @cached_property
    def alpha_free(self) -> BoolArray:
        mask = np.full((self.M, self.M), self.free_alpha, dtype=bool)
        if self.zero_diagonal and self.free_alpha:
            np.fill_diagonal(mask, False)
        return mask

    @cached_property
    def beta_free(self) -> BoolArray:
        return (
            np.ones(self.beta_shape, dtype=bool)
            if self.free_beta
            else np.zeros(self.beta_shape, dtype=bool)
        )

    @cached_property
    def mu_idx(self) -> IndexArray:
        return np.flatnonzero(self.mu_free)

    @cached_property
    def alpha_idx(self) -> IndexArray:
        return np.flatnonzero(self.alpha_free.ravel())

    @cached_property
    def beta_idx(self) -> IndexArray:
        return np.flatnonzero(self.beta_free.ravel())

    @cached_property
    def n_mu(self) -> int:
        return int(self.mu_idx.size)

    @cached_property
    def n_alpha(self) -> int:
        return int(self.alpha_idx.size)

    @cached_property
    def n_beta(self) -> int:
        return int(self.beta_idx.size)

    @cached_property
    def n_params(self) -> int:
        return self.n_mu + self.n_alpha + self.n_beta

    @cached_property
    def slices(self) -> tuple[slice, slice, slice]:
        """Row ranges of each family inside the flat vector, in order."""
        a = self.n_mu
        b = a + self.n_alpha
        return slice(0, a), slice(a, b), slice(b, self.n_params)

    @cached_property
    def names(self) -> tuple[str, ...]:
        """Coordinate name per flat index, for messages that must be locatable."""
        mu = [f"mu[{i}]" for i in self.mu_idx]
        alpha = [f"alpha[{i},{j}]" for i, j in zip(*np.nonzero(self.alpha_free), strict=False)]
        beta = (
            [f"beta[{j}]" for j in self.beta_idx]
            if self.shared_decay
            else [f"beta[{i},{j}]" for i, j in zip(*np.nonzero(self.beta_free), strict=False)]
        )
        return tuple(mu + alpha + beta)

    def _template_mu(self) -> FloatArray:
        return (
            np.array(self.mu_const, dtype=np.float64, copy=True)
            if self.mu_const is not None
            else np.zeros(self.M)
        )

    def _template_alpha(self) -> FloatArray:
        return (
            np.array(self.alpha_const, dtype=np.float64, copy=True)
            if self.alpha_const is not None
            else np.zeros((self.M, self.M))
        )

    def _template_beta(self) -> FloatArray:
        return (
            np.array(self.beta_const, dtype=np.float64, copy=True)
            if self.beta_const is not None
            else np.zeros(self.beta_shape)
        )

    def unpack_natural(self, x: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Scatter a natural-space free vector into full parameter arrays.

        Non-free entries keep whatever the layout was built with, so a fixed
        block is the same value in every call the optimizer makes.
        """
        s_mu, s_alpha, s_beta = self.slices
        mu = self._template_mu()
        alpha = self._template_alpha()
        beta = self._template_beta()
        mu[self.mu_idx] = x[s_mu]
        alpha.ravel()[self.alpha_idx] = x[s_alpha]
        beta.ravel()[self.beta_idx] = x[s_beta]
        return mu, alpha, beta

    def unpack_log(self, theta: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Scatter a log-space free vector into full natural-space arrays."""
        return self.unpack_natural(np.exp(theta))

    def pack_natural(self, mu: FloatArray, alpha: FloatArray, beta: FloatArray) -> FloatArray:
        s_mu, s_alpha, s_beta = self.slices
        x = np.empty(self.n_params)
        x[s_mu] = np.asarray(mu)[self.mu_idx]
        x[s_alpha] = np.asarray(alpha).ravel()[self.alpha_idx]
        x[s_beta] = np.asarray(beta).ravel()[self.beta_idx]
        return x

    def restrict_gradient(
        self, dmu: FloatArray, dalpha: FloatArray, dbeta: FloatArray
    ) -> FloatArray:
        """Free entries of a full gradient, in flat order."""
        return self.pack_natural(dmu, dalpha, dbeta)

    def scatter(self, x: FloatArray, family: str, fill: float = 0.0) -> FloatArray:
        """Place a free vector back into a full-shape array, ``fill`` elsewhere."""
        shape = {
            "mu": (self.M,),
            "alpha": (self.M, self.M),
            "beta": self.beta_shape,
        }.get(family)
        if shape is None:  # pragma: no cover - the family set is closed
            raise KeyError(family)
        index = {
            "mu": self.mu_idx,
            "alpha": self.alpha_idx,
            "beta": self.beta_idx,
        }[family]
        out: FloatArray = np.full(int(np.prod(shape)), fill, dtype=np.float64).reshape(shape)
        flat = out.reshape(-1)
        flat[index] = x
        return flat.reshape(shape)
