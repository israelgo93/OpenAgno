<!-- Keep the PR small and focused. One change per PR. -->

## Summary

<!-- What does this PR change? Why? Link the related issue when available. -->

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Refactor (no behavior change)
- [ ] Docs
- [ ] Chore (CI, tooling, deps)

## Impact area

- [ ] CLI
- [ ] Runtime (FastAPI / AgentOS)
- [ ] Channels
- [ ] Knowledge / PgVector
- [ ] MCP
- [ ] Templates
- [ ] Docs
- [ ] Deployment

## Checklist

- [ ] `ruff check` is clean
- [ ] `pytest -q` passes
- [ ] Updated docs (`docs/*.mdx` and `docs/es/*.mdx` when applicable)
- [ ] Updated `.env.example` if a new env var is introduced
- [ ] No secret material committed
- [ ] Runtime boundary with OpenAgnoCloud still honored (if the PR touches routes or contract)

## Testing notes

<!-- How did you validate the change locally? Paste commands, smoke steps, or a screenshot of the runtime log. -->
