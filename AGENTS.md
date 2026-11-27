# Agent instructions for this repository

These instructions apply in addition to the shared development environment
instructions. Repository-specific rules here take precedence for work in this
repository where they are more specific.

## Demo mode

The user runs live demos ("how I develop Ansible code with AI support") and
switches with the exact phrases `demo mode on` and `demo mode off`.

### 1. Switching and screen

- On `demo mode on`, reply with exactly about 40 lines that each contain a
  single dot `.`, separated by empty lines (Markdown joins consecutive lines
  into one paragraph), followed by the single line
  `Ready to build Ansible Automation content`. Nothing else in that reply.
- Demo mode stays active for every following message until the user writes
  `demo mode off`.
- On `demo mode off`, return to the normal working style and, when useful,
  report what happened during the demo (timings, issues).

### 2. Behaviour during the demo

- Treat each instruction as a fresh request. Do not mention earlier
  preparation, rehearsals, agreements, previous artifacts or timings.
- Explain briefly for an audience what is being done and why, and show the
  generated code.
- When explaining code line by line, always show the code line itself next to
  its one-line explanation, keeping the original indentation visible (table:
  line number, code, what it does). Short, no essays.
- Keep task tracking and bookkeeping silent.
- All safety, permission and approval rules still apply. If something blocks,
  say so plainly.

### 3. Targets, approval and scope

- Work only on the test AAP instance the user designates for demos; never on
  production.
- Repositories the user asks to set up in demo mode are created **public**.
  They contain generic code only: no hostnames, IP addresses, credentials or
  other environment-specific values.
- Create exactly what the current instruction asks for, one step per
  instruction. Never create follow-up objects automatically (no job template
  with a playbook, no rulebook activation with a rulebook). Objects strictly
  required by the requested one, such as the project a requested job template
  needs, are fine.
- The audience must see that a human approves generated content first: show
  the code, wait for the user's approval, and only then put it into AAP. The
  message is "AI generates, a human approves, AAP executes".
