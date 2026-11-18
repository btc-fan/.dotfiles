# 11: secret-scan keeps real keys out, stops fake test values

**What to build:** secret-scan still blocks a real key, token or password before commit and push, but stops blocking fake test values. Measured 2026-11-18: about 25 blocks in 7 days, 14 of 14 sampled were test values (`adminpass123`, `AIzaSECRET-test-key`), some from master content scanned again on a merge.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] gitleaks is installed by the dev-mac profile on all 3 machines (this Mac, oldmac, ubuntu01).
- [ ] Only added lines are scanned. Content that is already on the default branch is never scanned again on a merge.
- [ ] Test fixture paths (tests/, fixtures/, test data folders) use a stricter pattern: only real key shapes block there (provider prefixes with real length and entropy), not assigned words like `password = "x"`.
- [ ] Red: a real-shape key in app code blocks. Green: the 14 sampled values pass.
