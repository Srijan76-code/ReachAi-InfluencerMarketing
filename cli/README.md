# reachai

Connect your AI agent (Claude Code, Codex, Cursor) to your ReachAI account with one approval in the browser. No dependencies; Node 18 or newer.

```bash
npx reachai login            # shows a code, you approve it in your browser, your agent apps are set up
npx reachai status           # credits, Gmail, payments
npx reachai doctor           # checks a live ReachAI with your key; never sends or spends
npx reachai doctor --grant   # also asks for one permission and waits for you to approve it
npx reachai connect          # how to add ReachAI to any agent app by hand
npx reachai logout           # forget the saved key on this computer
```

The key is saved in `~/.config/reachai/credentials.json` (only you can read it). Remove it for good on the Agents page of ReachAI.
Set `REACHAI_URL` (or pass `--url`) to point at a different ReachAI.

Tests: `npm test`.
