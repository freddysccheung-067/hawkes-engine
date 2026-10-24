# Security policy

hawkes-engine is pre-alpha. The last release is 0.1.0 and only the `main` branch is
maintained; a fix for a security defect ships in a patch release rather than being
backported to an earlier version.

## Reporting a vulnerability

Please do not open a public issue with exploit details. Use GitHub's private
vulnerability reporting for this repository (the Security tab, "Report a
vulnerability") if it is enabled. If it is not, open a public issue that says only
that you have a security report, without technical detail, and a private channel
will be arranged there.

## What is in scope

The compiled core parses NumPy buffers in C++ and runs without the GIL, so the
reports that matter most are memory-safety defects: an out-of-bounds read or write,
a use-after-free, or an unvalidated length or index reachable from the Python API.
The C++ tests run under AddressSanitizer and UndefinedBehaviorSanitizer in CI, which
reduces that risk and does not remove it.

Also in scope: the build and packaging scripts, and the GitHub Actions workflows.

## What is not

Statistical findings about the estimator, such as the reported standard errors
understating sampling spread, are documented behaviour and not vulnerabilities. See
the [Limits page](docs/limits.md). Report disagreements with them as ordinary
issues.

## Response

This is a single-maintainer project. A report will be acknowledged when seen, with
no guaranteed response time.
