# Coordination hub

Sprint branch: **`feat/deterministic-stack-v2`**

| File | Who reads | Purpose |
|------|-----------|---------|
| [ARCHITECT_CONTEXT.md](ARCHITECT_CONTEXT.md) | Architect (every session) | Decisions, scope, status |
| [CODER_TASKS.md](CODER_TASKS.md) | Coder | Implementation checklist |
| [TESTER_GUIDE.md](TESTER_GUIDE.md) | Tester (you) | When to test, env vars |
| [TEST_RESULTS.md](TEST_RESULTS.md) | You paste UI/terminal | Architect reviews rounds |
| [AGENT_ROUTER.md](AGENT_ROUTER.md) | **You** | Which Cursor agent to prompt next |

**Preflight CLI:** `python scripts/preflight_tester.py <document>`

**Workflow:** BUILD slice → TEST slice → you paste UI → `review Round N` to architect.
