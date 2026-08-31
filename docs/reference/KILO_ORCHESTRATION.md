# Kilo orchestration reference

This runbook describes the repository's optional read-only Kilo reconnaissance
and contract-review workflow. It is stable tooling guidance, not task
authorization, research evidence, or permission to broaden an implementation.
`AGENTS.md`, `STATE.md`, and `TASK.md` retain their normal authority.

## Roles and ownership

The intended workflow is:

```text
GLM-5.3 Flash explorer
    -> compact reconnaissance
GPT-5.6 Luna Max through Codex
    -> implementation, debugging, and tests
GPT-5.6 Sol XHigh through Codex when explicitly requested and available
    -> premium independent review
Luna
    -> evaluates and fixes valid findings
```

When the Codex-native Sol review is unavailable or an external GLM review is
requested, use this fallback:

```text
GPT-5.6 Luna Max through Codex
    -> implementation and tests
GLM-5.3 contract reviewer
    -> independent read-only findings
Luna
    -> evaluates and fixes valid findings
```

The primary Codex agent remains responsible for every change and conclusion.
Explorer and reviewer output is advisory. It cannot authorize work, establish
acceptance evidence, or replace the primary agent's own verification.

The repository does not configure the primary Codex model through Kilo. Model
selection and reasoning effort for Luna or Sol belong to the Codex session.

## Project files

- `.kilo/explore.ps1` is the headless reconnaissance entry point.
- `.kilo/review.ps1` is the headless current-diff review entry point.
- `.kilo/agents/contract-reviewer.md` defines the reviewer prompt, model,
  finite step limit, and read-only permissions.
- `.kilo/kilo.example.jsonc` is the tracked, credential-free project
  configuration template.
- `.kilo/kilo.jsonc` is the active local configuration. It is intentionally
  ignored and must never contain a credential that could be copied into a
  tracked file.

The active configuration preserves indexing, overrides the built-in `explore`
subagent, restricts the built-in `ask` agent to a read-only bridge, and defines
the `codex-explore` and `codex-contract-review` commands.

## Agent and command names

There is one explorer agent, named `explore`. `codex-explore` is a command, not
a second agent.

Kilo CLI 7.5.6 does not accept a subagent as the root `kilo run` agent. The
wrappers therefore start the built-in primary `ask` agent and invoke a custom
command with `subtask: true`:

```text
explore.ps1
    -> ask primary bridge
    -> codex-explore command
    -> explore subagent
    -> compact result on stdout
```

The same bridge dispatches `codex-contract-review` to `contract-reviewer`.
The project-local `ask` override is deliberately narrow: it can read and
search, and it can dispatch only these two subagents. It cannot edit, write,
use a shell, access the web, or delegate to arbitrary agents.

## Effective Kilo configuration

| Role | Model | Variant | Steps | Mutation permissions |
| --- | --- | --- | ---: | --- |
| Explorer | `openrouter/z-ai/glm-5.3-flash` | `max` | 20 | None |
| Contract reviewer | `openrouter/z-ai/glm-5.3` | `max` | 30 | None |

The explorer can use targeted read, glob, grep, list, and semantic-search
operations. It cannot use the shell or delegate.

The contract reviewer has the same repository-reading capabilities plus
narrow read-only access to `git status`, `git diff`, `git log`, and `git show`.
All other shell commands are denied. Both agents deny environment-secret reads,
file mutation, web access, background work, commits, pushes, and additional
delegation.

## Fresh-session setup

Start with the normal repository context gate in `AGENTS.md`. Then verify that
the Kilo CLI is either on `PATH` or supplied by the installed Kilo VS Code
extension.

If `.kilo/kilo.jsonc` is absent, create it from the tracked template without
overwriting an existing local configuration:

```powershell
if (-not (Test-Path -LiteralPath .\.kilo\kilo.jsonc)) {
    Copy-Item -LiteralPath .\.kilo\kilo.example.jsonc `
        -Destination .\.kilo\kilo.jsonc
}
```

Keep provider credentials in Kilo's secure global configuration or supported
credential store. Do not add API keys, bearer tokens, or private identity to
the local template or tracked repository.

The wrappers can resolve the CLI from `PATH` or the newest installed Kilo VS
Code extension. Use the same resolution rule before direct validation:

```powershell
$kilo = Get-Command kilo -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty Source

if (-not $kilo) {
    $kilo = Get-ChildItem -LiteralPath `
            (Join-Path $env:USERPROFILE ".vscode\extensions") `
            -Directory -ErrorAction SilentlyContinue |
        Where-Object Name -Like "kilocode.kilo-code-*" |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object { Join-Path $_.FullName "bin\kilo.exe" } |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}

if (-not $kilo) {
    throw "Kilo CLI was not found."
}

& $kilo config check
& $kilo agent list
& $kilo debug agent explore
& $kilo debug agent contract-reviewer
```

The resolved definitions must show `explore` and `contract-reviewer` as
subagents, the models and variants in the table above, and no edit/write/task
permissions. The reviewer may show shell availability only for its explicit
read-only Git allowlist.

## Invocation

Run reconnaissance from the repository root and provide a concrete question:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\.kilo\explore.ps1 `
    "Locate the source, tests, callers, and contracts relevant to this task."
```

Run the independent reviewer after implementation and primary verification:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\.kilo\review.ps1
```

The explicit process-local execution-policy bypass is required on machines
that block direct `.ps1` execution. It does not change the machine-wide policy.

When Codex launches a wrapper, the textual result returns on stdout and can be
evaluated in the same session. If a person launches it in another terminal,
the result is not automatically added to Codex context and must be supplied to
the primary agent separately.

The explorer wrapper exits `2` for a missing question and `127` when no Kilo
CLI can be resolved. Both wrappers propagate a nonzero Kilo invocation exit.

## Normal operating sequence

1. Establish current truth and authorization from `STATE.md` and `TASK.md`.
2. Check the working tree and preserve existing user changes.
3. Run the explorer when repository reconnaissance would materially reduce
   uncertainty or primary-context noise.
4. Independently inspect the cited paths and evaluate the explorer handoff.
5. Implement only the authorized task and complete its focused and broader
   verification gates.
6. Use a Codex-native Sol review only when explicitly requested and available;
   otherwise run the Kilo contract reviewer when an external review is wanted.
7. Evaluate every finding against source, tests, contracts, and current scope.
   Fix only findings that are valid and authorized, then rerun affected checks.
8. Recheck the final diff and status. Do not commit or push without explicit
   user authorization.

The contract reviewer examines the entire current uncommitted diff. If the
working tree contains unrelated user work, disclose that scope and do not
attribute all findings to the active task.

## Verification and troubleshooting

After changing Kilo configuration or agent definitions:

1. run `kilo config check`;
2. inspect both resolved agents with `kilo debug agent`;
3. parse or invoke both PowerShell wrappers;
4. run one harmless explorer query and one reviewer smoke when credentials and
   provider access are available;
5. compare `git status` and `git diff` before and after each smoke;
6. scan all tracked Kilo files for credentials and generated output; and
7. confirm no `kilo run` process remains after completion.

A persistent `kilo.exe serve` process owned by the VS Code extension is not a
wrapper leak. Investigate its parent and command line before stopping it.

If a future Kilo version permits direct headless execution of subagents, the
`ask` bridge may be reconsidered. Do not change the invocation design from
memory: inspect the installed CLI help, resolved agents, permissions, and live
read-only behavior first.
