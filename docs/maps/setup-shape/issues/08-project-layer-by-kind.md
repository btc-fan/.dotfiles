# 08: What the project layer holds for each kind of folder

Type: grilling
Status: open
Blocked by: 05

## Question

What does `ai-adopt` write into a notes folder, an app repo, a monorepo and a team repo that is not the owner's?

Facts: the folder `server-start` has no code and got the full layer (15 skill links for each agent, a regression
ledger, a test ratchet, coding standards, a UI rule, a Serena file with no language). A monorepo gets no check
target, and its Done text still asks for one. In a repo with its own AI setup the adopt reports no conflict. The
PR gate asks for the owner's template in each repo.

Decide the kinds, what each kind gets, and who chooses the kind (the tool from the content, or the owner with a
flag). Decide what holds in a repo that is not adopted and in a team repo: all global gates, or the safety gates
only.

Read first: report sections 8, 9 and 12.
