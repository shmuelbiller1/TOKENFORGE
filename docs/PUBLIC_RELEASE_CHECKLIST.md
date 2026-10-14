# Public release review

- [x] Remove generated codebase snapshots and credential test notes from current tree.
- [x] Eliminate seeded default admin credentials and resetting an existing admin.
- [x] Require an explicit, long JWT secret and secure first-run admin password.
- [x] Set SameSite=Lax cookies and check browser request origin.
- [x] Remove external scripts, hosted analytics, and generated-platform branding.
- [x] Namespace the API cache by account and preserve filenames and file order.
- [x] Bound uploaded bytes before buffering an oversized file.
- [x] Add local desktop GUI, build workflow and smoke tests.
- [ ] Rotate administrator credentials published in earlier commits or environments.
- [ ] Review git history for retained secrets: deletion does NOT erase history.
- [ ] Run and verify hosted integration tests against a real database.
- [ ] Verify clean offline desktop launch on Windows, macOS and Linux.
- [ ] Sign and notarize desktop packages for fewer OS warnings.
- [ ] Commit a reviewed frontend lockfile for repeatable installs.
- [ ] Review package audits and deployed hosting configuration.
- [ ] Decide whether MIT permits the redistribution rights you want.
