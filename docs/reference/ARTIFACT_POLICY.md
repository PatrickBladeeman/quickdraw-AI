# Research artifact and evidence policy

## Principle

Keep reproducibility inputs and curated conclusions in Git; keep large,
machine-specific, sensitive, or regenerable outputs outside tracked source.
Every published number should remain traceable to a run manifest, source
contract, exact command, and relevant hashes.

## Track

- source code and tests;
- exact dependency locks and versioned research contracts;
- JSON schemas and validators;
- run and analysis scripts;
- small sanitized manifest examples;
- curated aggregate tables, figures, checksums, and conclusions;
- evidence summaries that preserve negative, null, flaky, and rejected results;
- third-party license and citation records.

## Keep generated and ignored

Use `Artifacts/Experiments/` for generated experiment state, including:

- raw JSONL and CSV traces;
- run manifests containing machine-specific execution details;
- checkpoints, ONNX exports, and model outputs;
- Python environments and reconstructed wheels;
- standalone players, build logs, and Unity test output;
- temporary comparisons, diagnostic traces, and watch-mode output.

Generated artifacts do not become acceptance evidence merely because they exist.
An owning validator or curated evidence record must state which files were
accepted and why.

## Never commit

- credentials, tokens, private keys, or authentication-bearing command lines;
- private identity, background, or local-session context;
- paid, proprietary, or otherwise non-redistributable assets;
- local model weights unless their license and an explicit artifact task allow it;
- raw logs or crash output containing more sensitive context than the claim needs;
- caches, IDE state, disposable environments, or accidental build products.

Model source, quantization, runtime version, settings, and SHA-256 belong in a
manifest even when the weight file remains outside Git.

## Evidence handling

- Preserve exact seeds, versions, contract hashes, checkpoint lineage, trace
  hashes, and analysis commands.
- Keep timing results with their measurement boundary; do not relabel transport
  throughput as training or model throughput.
- Keep software-contract, integration, performance, and research-effectiveness
  claims separate.
- Preserve failures and rejected runs. State whether a retry addressed code,
  environment, tooling, or operator behavior.
- Do not weaken a registered threshold after viewing a result unless the change
  is separately approved and clearly exploratory.
- Diagnostic watch mode produces observational output, not two-process
  acceptance evidence.

## Cleanup safety

Generated and ignored does not mean disposable without inspection. Before
cleanup, resolve exact paths, verify that curated evidence and required hashes
have been preserved, and avoid broad recursive targets. Cleanup requires its own
authorization when it is not part of the current task.

See [`AGENTS.md`](../../AGENTS.md) for repository safety rules and
[`docs/evidence`](../evidence/README.md) for curated milestone records.
