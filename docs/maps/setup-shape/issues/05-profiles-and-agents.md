# 05: Which profiles and agents the setup keeps

Type: grilling
Status: open
Blocked by: none

## Question

Which of these stay in the code: the `server` profile with its gates (no-sudo, no-destroy,
audit-before-install), the root layer, the box plugin, Hermes, opencode?

`routing.yaml` says that dev-mac is the profile of all 3 machines. If that is true, about 2,500 lines of code and
about 4,000 lines of test cases are reached only by tests. Decide per item: keep (name the machine that runs it),
park on a branch, or delete.

Also decide the tier: the code always returns "long". Either the tier comes back with a real meaning (see the
ticket on the project layer), or its code goes.

Read first: report section 7.
