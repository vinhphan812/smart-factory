# Smart Factory — Documentation Index

This is the engineering documentation hub for AIBOT Smart Factory. Read [Project Context](PROJECT_CONTEXT.md) first and [Agent Guidance](../AGENTS.md) before coding.

| Document | Purpose |
|---|---|
| [Project context](PROJECT_CONTEXT.md) | Identity, objectives, hardware/software readiness, evidence boundaries |
| [Repository layout](architecture/repository-layout.md) | Module map, purpose, contracts, ownership and design decisions |
| [Architecture](architecture/overview.md) | Three systems, integration flows, existing versus target interfaces |
| [Components](architecture/components.md) | Responsibility boundaries and module contracts |
| [Integration contracts](contracts-and-data.md) | AMLP/MQTT reality and proposed canonical schema |
| [Development](development.md) | Setup, contributor workflow, toolchains |
| [Testing](testing-and-acceptance.md) | Test levels, cases, DoD, evidence |
| [Roadmap](ROADMAP.md) | 12-month sequencing and issue map |
| [Risks](risks.md) | Hardware, safety, software and research risk register |
| [Research/training](research-and-training.md) | Experiments, labs and deliverables |
| [Experiment baselines](experiment-baselines.md) | Reproducible experiment designs, baselines and runbook |

## Source precedence
1. Current source code and passing tests define **what is implemented**.
2. `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` and `esp32-ukit-bridge/docs/mqtt-contract.md` define the existing documented bridge interfaces; check source for discrepancies.
3. The 12-month scientific proposal defines the research targets.
4. Issues and future architecture notes are **plans**, not delivered features.

**Rule:** always distinguish **implemented**, **simulated**, **planned**, **hardware blocked** and **hardware validated**. Do not silently replace an actual protocol with a proposal.
