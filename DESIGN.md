# Healthcare Appointment Scheduling Benchmark Design

## 1. Overview

This benchmark evaluates whether AI agents can safely reschedule healthcare
appointments while following scheduling, insurance, specialty, referral,
authorization, age-eligibility, and availability constraints.

I used Flight Bench as a reference for the general benchmark workflow:

Task → Agent Runner → Tools → Controlled Environment → Trace and Final State
→ Deterministic Grader → Report

The general structure was adapted from the existing benchmark, while the
healthcare data, tasks, tools, failure scenarios, and grading rules were
designed specifically for this project.

## 2. Do We Need MCP?

MCP is not strictly required. A normal HTTP API or direct function API would
also be sufficient, as long as agents can access the tools and the benchmark
can record their actions.

I used MCP because Claude and Codex can connect to local MCP tools through
their command-line interfaces. It provides a convenient way to expose the
same appointment operations to different agents.

In a general benchmark abstraction, MCP should be treated as the tool
transport layer rather than a required part of the benchmark. The task,
environment, tool semantics, and grader should remain independent of whether
the tools are exposed through MCP, HTTP, or direct function calls.

## 3. Environment Design

The benchmark uses a small synthetic clinic environment containing fictional:

- Patients
- Providers
- Provider specialties
- Insurance plans
- Referrals
- Authorization records
- Appointment slots
- Existing appointments

The environment contains a fixed clinic snapshot and a separate mutable
ledger for each run.

Before every agent-task run, the runner creates a fresh copy of the starting
state. This ensures that every agent receives the same environment and that
changes from one run do not affect another run.

The agent does not directly read the complete data files. Instead, the data is
exposed through appointment tools for operations such as:

- Checking the current appointment
- Retrieving patient and provider information
- Retrieving relevant policies
- Searching available slots
- Listing appointments
- Rescheduling an appointment
- Declining a request

The server also records tool calls and changes to the clinic state.

## 4. Synthetic Data and Task Creation

The clinic data and tasks were created with GPT assistance and manually
reviewed. All patients, providers, appointments, and records are fictional,
and no real patient data is used.

I first identified common healthcare scheduling constraints and converted
them into structured records and task scenarios.

The easy tasks test basic constraints such as:

- Requested time
- Provider choice
- Insurance compatibility
- Specialty matching
- Slot availability
- Selecting the earliest valid option

The hard tasks introduce more complex mechanisms such as:

- Policy retrieval
- Conditional no-op behavior
- Expired referrals
- Changing availability during booking
- Double-booking prevention
- Multiple simultaneous constraints
- Authorization safety
- Pediatric eligibility

For example, H04 tests recovery when the environment changes. The first valid
slot appears available during search but becomes unavailable when the agent
tries to book it. The agent must recognize the failure and choose the next
valid slot.

Most current tasks have one expected outcome. A future version should include
tasks with multiple safe solutions and allow any outcome that satisfies the
required constraints.

## 5. Common Task Pattern

Most tasks follow the same general pattern:

1. Inspect the current appointment.
2. Retrieve relevant patient, provider, or policy information.
3. Search for candidate appointment slots.
4. Filter candidates using hard constraints.
5. Select the best valid option.
6. Reschedule, decline, or make no change.
7. Confirm the final clinic state.

Hard tasks modify this pattern by introducing policy rules, conflicting
constraints, unsafe requests, missing information, or tool failures.

## 6. Agent Harness

This benchmark uses a lightweight CLI-based harness rather than a browser
harness.

For each run, the runner:

1. Loads one task.
2. Resets the clinic environment.
3. Starts the appointment MCP server.
4. Sends the task to the selected agent.
5. Gives the agent access to the appointment tools.
6. Records the server-side tool calls.
7. Saves the final clinic state.
8. Runs the deterministic grader.
9. Saves the result for reporting.

Claude and Codex currently use different CLI harnesses. Therefore, the
current evaluation compares complete agent products rather than providing a
fully controlled comparison of foundation models.

## 7. Grading

The expected behavior for each task is defined before the agent is run.

The deterministic grader checks:

- Whether the appointment reached the expected final state
- Whether scheduling constraints were satisfied
- Whether the correct reschedule, decline, or no-op occurred
- Whether unrelated appointments were changed
- Whether an unsafe action occurred
- Tool-call count
- Failed tool-call count
- Execution time
- Important trace events for selected hard tasks

For H04, the grader checks the correct final slot and expects evidence of a
booking failure and recovery. Codex reached the correct final slot, but the
expected recovery event did not appear in the trace.

This reveals an open design question: should a safe and correct final outcome
be enough, or should the benchmark also require evidence of a particular
recovery process?

A future grader should report separate metrics for:

- Final-outcome correctness
- Constraint satisfaction
- Safety
- Recovery
- Efficiency

## 8. Preliminary Results

I evaluated Claude Haiku, Claude Sonnet, and Codex on six easy tasks and eight
hard tasks.

All three agents passed the easy tasks. Sonnet passed all eight hard tasks,
while Haiku and Codex each failed one.

These results should not be treated as a definitive agent ranking because the
task set is small and each agent-task pair was only run once.

The main preliminary finding is that basic scheduling tasks were too easy to
distinguish the agents. Differences appeared when the hard tasks introduced
specific failure mechanisms such as policy reasoning, combined constraints,
and recovery from a changing environment.

## 9. Current Limitations

- Only fourteen tasks
- Each agent-task pair was run once
- Small handcrafted synthetic clinic environment
- Easy-task ceiling effect
- Different harnesses for Claude and Codex
- Most tasks have only one accepted outcome
- Some trace-based grading requirements may be too strict
- Pass/fail does not represent the severity of errors
- Real healthcare systems contain more uncertainty and incomplete information

## 10. Next Steps

- Run every task multiple times
- Add more realistic and ambiguous requests
- Add incomplete-information and clarification scenarios
- Support multiple acceptable outcomes
- Add more adversarial authorization scenarios
- Add waitlists, cancellations, and multi-appointment tasks
- Separate outcome, safety, recovery, and efficiency metrics
- Identify benchmark components that can be standardized across domains