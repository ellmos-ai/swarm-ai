# Release Gate - Pre-Public Checklist

**Status:** LOCKED

> This repository is **not ready for public release**.
> All modules must pass thorough testing before the visibility can be changed to public.

---

## Pre-Release Checklist

- [ ] All 5 swarm patterns tested (with real API calls)
- [ ] `summarize_chunks.py` end-to-end tested
- [ ] `consensus_swarm.py` end-to-end tested
- [ ] `benchmark.py` executed with current model
- [ ] No hardcoded API keys or secrets in any file
- [ ] No personal paths (`C:\Users\lukas`, etc.) in source code
- [ ] No BACH-specific database dependencies
- [ ] `README.md` up-to-date and accurate
- [ ] License header present in all source files

## Gating Rule

At least **80%** of the checklist items above must be completed (green) before this repository may be set to public.

## Responsible

**Lukas Geiger** ([github.com/lukisch](https://github.com/lukisch))
