# ADR-008: License

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

hawkes-engine is an open-source numerical library for quantitative finance, computational neuroscience, and social network analysis. The license determines: (1) who can use it, (2) whether derivatives must be open-sourced, (3) whether it can be embedded in commercial products. The choice is irreversible post-publication: relicensing requires consent from all contributors.

Common licenses:
- **Permissive** (MIT, BSD, Apache 2.0): Allow commercial use, modification, redistribution. No copyleft. Users can close-source derivatives.
- **Weak copyleft** (LGPL): Derivatives of the library itself must be open, but programs *using* the library can be closed.
- **Strong copyleft** (GPL): Any program linking the library must be open-sourced. Kills commercial adoption.

Target users: quant trading firms, academic researchers, data scientists. Quant firms cannot use GPL (their trading strategies are proprietary, and GPL forces disclosure). Academic researchers prefer permissive (easier to cite, fewer legal questions). Data scientists want pip-installable without license friction.

Competitor landscape: NumPy, SciPy, scikit-learn all use BSD (permissive). PyTorch uses BSD-3-Clause. TensorFlow uses Apache 2.0 (permissive + patent grant). statsmodels uses BSD. No major scientific Python library uses GPL.

Patent grant: Apache 2.0 includes an explicit patent grant (contributors grant patent licenses to users). MIT/BSD do not. For a numerical library (unlikely to have novel patentable algorithms), this is low-value. Hawkes processes are prior art (1971), and the recursion is Ozaki (1979). No patent risk.

## Decision

**MIT License**

Full text:
```
MIT License

Copyright (c) 2026 Freddy Shi Chun Cheung

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Why MIT**:
- **Maximum adoption**: No friction for commercial, academic, or hobbyist use
- **Quant-firm compatible**: Firms can embed hawkes-engine in proprietary trading systems without disclosing source
- **Simple and well-understood**: Shortest widely-recognized permissive license (171 words vs BSD-3's 213 words vs Apache 2.0's ~3000 words)
- **Ecosystem match**: NumPy, SciPy, pandas, scikit-learn are all BSD/MIT (similar). Users expect permissive licenses in scientific Python.

**Contributor policy**: All contributions (PRs) implicitly licensed under MIT. Add CONTRIBUTING.md stating: "By submitting a pull request, you agree to license your contribution under the MIT License."

## Alternatives Considered

### Option 1: Apache 2.0
- **Pros**: Explicit patent grant (contributors can't later sue users for patent infringement), used by TensorFlow, PyTorch (originally), more "corporate-friendly" in legal perception
- **Cons**: 10脳 longer license text (harder to read), patent clause is overkill for this library (Hawkes processes are prior art, no novel algorithms to patent), less recognizable to academic researchers than MIT/BSD
- **Why rejected**: Patent grant is unnecessary here. The recursion (Ozaki 1979) and simulators (Ogata 1981) are public domain. Apache 2.0's complexity exceeds its benefit. Use MIT for simplicity.

### Option 2: BSD-3-Clause
- **Pros**: Nearly identical to MIT (also permissive), used by NumPy/SciPy/scikit-learn, includes explicit "no endorsement" clause (can't use author's name in ads)
- **Cons**: Slightly longer than MIT (213 vs 171 words), "no endorsement" clause is redundant (trademark law already covers this), less recognizable by name (people say "MIT" more than "BSD")
- **Why rejected**: Functionally identical to MIT. MIT is shorter and more widely recognized by non-lawyers. The "no endorsement" clause has never mattered in practice (no one advertises "approved by NumPy authors").

### Option 3: GPL v3 (strong copyleft)
- **Pros**: Ensures all derivatives are open-source (prevents proprietary forks), some ideological preference for copyleft
- **Cons**: Kills commercial adoption. Quant firms cannot use GPL libraries (linking GPL code forces the entire trading system to be open-sourced, disclosing strategies). Academic adoption also suffers (researchers embedding in proprietary tools must relicense). NumPy/SciPy/scikit-learn avoid GPL for this reason.
- **Why rejected**: The goal is maximum adoption, not ideological purity. A GPL library with zero users has less impact than an MIT library used by 100 firms. Users who want to open-source derivatives can do so voluntarily.

### Option 4: Dual-license (MIT for open-source, commercial license for closed-source)
- **Pros**: Revenue stream (sell commercial licenses to firms that want support/indemnification), used by some databases (MySQL, Qt)
- **Cons**: Administrative overhead (track who bought what), legal complexity (enforce commercial terms), reduces adoption (firms hesitant to negotiate), not a fit for a solo/academic project (who handles sales?), community distrust (are we open-source or a commercial product?)
- **Why rejected**: This is a research library, not a product. The goal is citation impact, not revenue. Dual-licensing makes sense for venture-backed companies (MongoDB, Elastic), not academic side projects.

## Consequences

**Positive**:
- **Maximum adoption**: No license friction. Firms, academics, hobbyists can all use it without legal review.
- **Quant-firm compatible**: Proprietary trading systems can embed hawkes-engine without disclosing source. This is the primary use case (HFT order flow modeling).
- **Citation-friendly**: Academics prefer permissive licenses (easier to justify in grant proposals, no GPL contamination risk).
- **Ecosystem fit**: Matches NumPy, SciPy, pandas, scikit-learn. Users expect MIT/BSD in scientific Python.

**Negative**:
- **No copyleft**: A firm could fork, improve, and never contribute back. This is acceptable: the goal is impact, not control. If a firm's fork is better, they can keep it (and maintain it forever). Most firms prefer upstream contributions (less maintenance burden).
- **No patent grant**: Unlike Apache 2.0, MIT doesn't explicitly grant patent licenses. But there are no patents to grant (prior art: Hawkes 1971, Ozaki 1979). If a contributor later claims a patent, they could sue users (unlikely, and trademark law covers this to some extent).

**Neutral**:
- **No warranty**: MIT includes "AS IS, NO WARRANTY" (standard for all open-source licenses). Users cannot sue for bugs (e.g., wrong likelihood causing a bad trade). This is expected and acceptable.
- **Attribution required**: MIT requires "The above copyright notice and this permission notice shall be included in all copies." Firms using the library must keep the LICENSE file (but don't need to advertise authorship).

## References

- [OSI-approved licenses](https://opensource.org/licenses/)
- [MIT License text](https://opensource.org/licenses/MIT)
- [Choose a License](https://choosealicense.com/) (GitHub's license guide)
- NumPy license: [BSD-3-Clause](https://github.com/numpy/numpy/blob/main/LICENSE.txt)
- scikit-learn license: [BSD-3-Clause](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING)
- TensorFlow license: [Apache 2.0](https://github.com/tensorflow/tensorflow/blob/master/LICENSE)
- GPL and quant finance: [Why financial firms avoid GPL](https://lwn.net/Articles/548680/)
