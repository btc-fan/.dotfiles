# Regressions

One line per bug that reached the `ai` branch, added in the fix PR together with a test that failed before the
fix. Format (one line, or wrapped with an indent; `area:` is a folder or file path, more than one with commas):

    R-001 | 2026-11-17 | area: ai/bin | symptom: ... | cause: ... | test: ai/tests/test_x.py::t_name | reopened: 0

Rules: never delete a line; `reopened` only goes up (the same symptom came back).

## Ledger

R-001 | 2026-11-17 | area: ai/bin/ai-start | symptom: ai-adopt left .ai/enabled, the Map check timing and a Libraries row uncommitted, and turned the Stop hook off on stray Markdown | cause: steps after the commit wrote tracked files; check-fast ran before the docs baseline | test: ai/tests/test_tier1.py::t_adopt_leaves_tree_clean | reopened: 0
R-002 | 2026-11-17 | area: ai/bin/ai-check-detect | symptom: an ai-adopt rerun dropped an owner flag in the managed Makefile block | cause: the rerun replaced the block with the detector output | test: ai/tests/test_tier1.py::t_plan_keeps_owner_flags | reopened: 0
R-003 | 2026-11-17 | area: ai/bin/ai-doctor | symptom: ai-doctor failed the RTK hook check with off in ~/.config/ai/rtk-hook | cause: ai-doctor did not read the owner switch that the installer reads | test: ai/tests/test_cleanup.py::t_rtk_off_doctor_bare_hook | reopened: 0
R-004 | 2026-11-17 | area: ai/marketplace/plugins/ai-core/hooks/router.py | symptom: pasted session output fired the diagnosing-bugs and tdd stop rules and blocked turns | cause: prompt rules matched pasted lines and product names | test: ai/tests/cases/diagnosing-bugs.json, ai/tests/cases/tdd.json, ai/tests/cases/ui.json (pasted cases) | reopened: 0
R-005 | 2026-11-17 | area: ai/marketplace/plugins/ai-core/hooks/router.py | symptom: a pasted merge line could set the merge OK; an agent hand-back fired prompt rules | cause: the merge OK read the prompt before the pasted-output filter; <agent-message> was not a notification | test: ai/tests/cases/merge-approval.json | reopened: 0
R-006 | 2026-11-17 | area: ai/bin/ai-start | symptom: an ai-adopt rerun dropped owner lines inside the Done, tool and .gitignore blocks, and --refresh-map dropped owner lines inside the Map | cause: the rerun replaced each managed block with the generator output | test: ai/tests/test_tier1.py::t_adopt_owner_text_survives_rerun | reopened: 0
R-007 | 2026-11-17 | area: ai/bin/ai-sync | symptom: a skill added to ai/skills (setup-rollout) was not linked after git pull on three machines; ai-doctor warned until install.sh ran | cause: only install.sh linked skills, ai-sync did not | test: ai/tests/test_commands.py::t_ai_sync_links_skills | reopened: 0
R-008 | 2026-11-17 | area: ai/bin/ai-sync | symptom: after git pull, the create- and maintain-verification-skill links pointed at the repo copy, not the newer audited pstack copy, on two machines | cause: ai-sync ran link_skills without the pstack_link step that install.sh runs after it | test: ai/tests/test_commands.py::t_ai_sync_keeps_pstack | reopened: 0
R-009 | 2026-11-18 | area: ai/marketplace/plugins/ai-core/hooks/hooklib.py | symptom: the owner wrote "merge go ahead" and the merge-approval gate still denied gh pr merge | cause: MERGE_OK_RX knew "go ahead and merge" and "merge it", not merge followed by go ahead | test: ai/tests/cases/merge-approval.json (R-009 cases) | reopened: 0
