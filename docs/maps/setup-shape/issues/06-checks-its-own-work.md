# 06: What "the agent checks its own work" means on dev-mac

Type: grilling
Status: open
Blocked by: 01

## Question

Which check must be green before an agent may end a turn that changed code, and how strict is it for a small
change?

Facts: the Stop check that runs `make check-fast` is off on dev-mac since 2026-11-15, on all 3 machines, and the
rules still say it runs. The verify hooks block a Stop 2 times, then let it pass. Each app-code change gets the
same verify wall, small or large. The kody project sizes the proof by a risk class from a script (tickets 08 and
09 of `setup-audit`).

Decide: the Stop check comes back on dev-mac, or its code goes. Decide if a failed check blocks or only tells
the owner. Decide if the proof is sized by risk.

Read first: report sections 3, 5 and 10.
