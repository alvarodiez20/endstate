# MCP and tool discovery

The harness in these docs ships six tools, hardcoded. Real deployments do not look like that. They
attach tools at runtime, from servers someone else wrote, and the number goes up every quarter.

That change — tools as a static list versus tools as a runtime catalogue — breaks three things that
worked fine at six tools.

!!! info "Status"

    `endstate` has **no MCP client** and will not get one; the tool registry is a dict built at
    startup ([`agent/tools/`](https://github.com/alvarodiez20/endstate/tree/main/src/endstate/agent/tools)).
    This page exists because the six-tool assumption is doing quiet work throughout the rest of this
    section, and it is worth knowing exactly which parts of the design depend on it.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/mcp-and-tool-discovery.html"
          height="710" loading="lazy"
          title="Tool schemas collapsing from 150,000 tokens to 2,000"></iframe>
</div>

## What MCP is, in one paragraph

The Model Context Protocol is an open standard for connecting agents to external systems. Instead of
writing an integration per (agent, service) pair, you implement the protocol once and get the
ecosystem. A **server** exposes tools; a **client** — your harness — discovers them, advertises them
to the model, and executes the calls the model makes. It launched in November 2024 and is now the
de-facto standard; there are thousands of servers.

That is the good part and it is genuinely good. The rest of this page is about what it costs.

## Problem one: tool definitions are always-on context

Every tool the model can call must have its schema in the context window, because that schema is how
the model knows the tool exists. Six tools is a rounding error. A production agent with a dozen MCP
servers attached is different:

```
gdrive.getDocument
     Description: Retrieves a document from Google Drive
     Parameters:
                documentId (required, string): The ID of the document to retrieve
                fields (optional, string): Specific fields to return
     Returns: Document object with title, body content, metadata, permissions, etc.
```

Multiply by a few hundred. Anthropic reports agents processing **hundreds of thousands of tokens of
tool definitions before reading the user's request** — paid on every step of every run, and
[degrading attention](context-and-compaction.md) on the tokens that actually matter.

This is the same economics as a tool `description`, which
[Tools and the sandbox](tools-and-sandbox.md) already flags as prompt engineering wearing a docstring
costume. MCP does not create the problem. It multiplies it by the size of the ecosystem.

## Problem two: intermediate results pass through the model twice

Ask an agent to copy a meeting transcript from Drive into Salesforce and the naive tool-calling shape
is:

```
TOOL CALL: gdrive.getDocument(documentId: "abc123")
        → returns the full transcript          (into context)

TOOL CALL: salesforce.updateRecord(data: { Notes: "<the full transcript again>" })
        → the model must write it back out     (into context, again)
```

For a two-hour meeting that is roughly 50,000 extra tokens for an operation that moves no
information the model needed to read. For a larger document it does not merely cost money — it
exceeds the window and the workflow breaks. And a model transcribing 50,000 tokens verbatim is a
model with 50,000 opportunities to make a copying error.

## Problem three: choosing between 400 tools

The context cost is the measurable failure. This one is the expensive one.

If a senior engineer on your team cannot say, without hesitation, which tool should be used in a
given situation, an agent cannot be expected to do better. Ambiguity in the tool taxonomy becomes
ambiguity in behaviour.

Bloated, overlapping tool sets produce ambiguous decision points, and the agent's failure mode is not
"no tool found" — it is picking the plausible wrong one and proceeding confidently. Two MCP servers
that both expose a `search` is not a hypothetical.

## The fix that is actually interesting: tools as files

The response to all three problems turns out to be the same one skills use — **progressive
disclosure**, applied to tool schemas instead of instructions.

Present the connected servers as a filesystem rather than as a list in the prompt:

```
servers
├── google-drive
│   ├── getDocument.ts
│   └── ...
├── salesforce
│   ├── updateRecord.ts
│   └── ...
└── ...
```

The agent lists `./servers/` to see what exists, reads only the two tool files it needs, and then
writes code that calls them:

```ts
const transcript = (await gdrive.getDocument({ documentId: 'abc123' })).content;
await salesforce.updateRecord({
  objectType: 'SalesMeeting',
  recordId: '00Q5f000001abcXYZ',
  data: { Notes: transcript },
});
```

The transcript never enters the context window. Anthropic measured this exact example at **150,000
tokens down to 2,000 — a 98.7% reduction**. Cloudflare arrived at the same design independently and
called it Code Mode.

The alternative shape, for harnesses without code execution, is a `search_tools` tool with a
detail-level parameter: names only, names and descriptions, or full schemas. Same principle, one
level of indirection instead of a filesystem.

## What that buys beyond tokens

| Benefit | Why it follows |
| --- | --- |
| Filtering before the model sees it | 10,000 spreadsheet rows become five, in code, not in context |
| Real control flow | Loops, retries and conditionals as code beat alternating tool calls and sleeps through the loop |
| Lower time-to-first-token | The execution environment evaluates the `if`, not the model |
| Privacy by default | Intermediate values stay in the sandbox unless explicitly logged; PII can be tokenised so it flows Drive → Salesforce without ever entering the transcript |
| State between steps | Write `leads.csv`, resume later — which is [durability](durability.md) by another name |

And it closes the loop back to [skills](skills.md): once an agent has written working code for a
task, saving it with a `SKILL.md` next to it turns a one-off into a capability. The agent
incrementally builds its own scaffolding.

!!! warning "Code execution is not free"

    Running model-generated code needs a sandbox with resource limits and monitoring — infrastructure
    that direct tool calls do not need. You are trading a token bill for an operational one. That
    trade is usually correct at scale and usually wrong at six tools, which is why this harness has
    not made it.

## What MCP does to the threat model

This is the part that is easy to skip and shouldn't be.

Direct tool calls have one trust boundary: the harness. MCP has one per server. Each server is
third-party code that can read the agent's arguments, return arbitrary text into the agent's context,
and change its own behaviour after you audited it.

More sharply: MCP is an ecosystem designed to make it easy to mix and match tools from different
sources. Many of those tools read private data. Many expose the agent to attacker-controlled text.
Many can make an outbound request. Combining them is exactly the [lethal trifecta](prompt-injection.md),
and the exploit Invariant Labs published against GitHub's official MCP server in May 2025 assembled
all three inside a *single* server: the agent read a malicious issue filed on a public repository,
followed its instructions into the private repositories the user had authorised, and leaked their
contents back out through a pull request. GitHub could not fix it server-side — the flaw is in the
agent system, not the server code.

The mitigations are ordinary and boring: enumerate what each server can reach, keep the
[permission policy](permissions.md) in front of the call rather than inside the server, and treat
every tool result as untrusted input rather than as fact.

## Why this harness stays at six tools

Not because MCP is wrong. Because the argument this project is making is about
[measuring end states](evaluation.md), and a fixed, small, auditable tool set is a control variable.
If the tool catalogue changes between runs, a cost table and a task pass-rate stop being comparable
to each other, and the benchmark stops meaning anything.

That is a decision about scope, not about the protocol. See [Non-goals](../design/non-goals.md).

## What to check in your own agent

- How many tokens of tool schema does a run pay before the user's first word? Measure it; the number
  is usually a surprise.
- Can two connected servers plausibly answer the same request? What breaks the tie?
- Do large tool results pass through the model, or can they be filtered where they are produced?
- For each server: private data, untrusted content, or outbound reach? How many of the three does
  your *whole* set add up to?

## Sources

- [Code execution with MCP: building more efficient AI agents](https://www.anthropic.com/engineering/code-execution-with-mcp) — Anthropic, November 2025
- [Model Context Protocol](https://modelcontextprotocol.io/) — the specification
- [Code Mode](https://blog.cloudflare.com/code-mode/) — Cloudflare
- [The lethal trifecta for AI agents](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) — Simon Willison, June 2025
