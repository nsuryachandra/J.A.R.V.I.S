# JARVIS — Personal AI Operating System

## 1. Document Control

### 1.1 Document purpose

This document defines the complete product, technical, behavioral, safety, deployment, and testing requirements for JARVIS.

JARVIS is a cloud-first, all-purpose personal AI operating system inspired by the useful qualities of a fictional intelligent assistant:

- Natural conversation.
- Long-term memory.
- Awareness of dates and time.
- Multimodal understanding.
- Cross-device operation.
- Tool use.
- Proactive assistance.
- Multi-agent delegation.
- Human-like continuity.
- Strong privacy and user control.

This document is the source of truth for product behavior and technical scope.

### 1.2 Document audience

This document is intended for:

- Product architects.
- AI engineers.
- Backend engineers.
- Frontend engineers.
- Security engineers.
- UX designers.
- QA engineers.
- DevOps engineers.
- Antigravity agents implementing the system.
- Future maintainers and contributors.

### 1.3 Product name

**JARVIS**

The name refers to the product concept only. The system must use original branding, original UI assets, original voice design, and original behavior. It must not imitate a copyrighted character, actor, trademark, voice, script, or protected visual asset.

### 1.4 Document status

- Status: Master product requirements document.
- Version: 1.0.
- Initial deployment target: Render.
- Initial AI providers: NVIDIA APIs and ElevenLabs APIs.
- Initial user timezone: Asia/Kolkata.
- Initial target location: Hyderabad, India.
- Initial deployment style: Cloud-first.
- Local AI model requirement: None for the first version.

### 1.5 Requirement language

The words below have precise meanings:

- **MUST:** Mandatory for the relevant release.
- **SHOULD:** Strongly recommended unless a documented reason exists not to implement it.
- **MAY:** Optional capability.
- **MUST NOT:** Prohibited behavior.
- **APPROVAL:** Explicit user permission for the exact proposed action.
- **SESSION:** A bounded interaction context with defined start and end.
- **MEMORY:** Persisted information intentionally stored for future use.
- **EVENT:** A time-associated occurrence or planned occurrence.
- **ROUTINE:** A repeated event pattern.
- **TASK:** Work that has a state, status, and possible next action.
- **AGENT:** A specialized reasoning and tool-using component.
- **TOOL:** A callable capability that can read data, transform data, or perform an action.
- **EXECUTION:** The act of calling an external system or modifying state.

***

## 2. Executive Summary

### 2.1 Product definition

JARVIS is a user-controlled, cloud-hosted, multimodal personal AI operating system.

It is not merely:

- A chatbot.
- A voice assistant.
- A business assistant.
- A task manager.
- A coding assistant.
- A browser automation tool.

It is a unified system that coordinates all of those capabilities through one persistent user identity, one memory layer, one permission system, and multiple specialized agents.

### 2.2 Core promise

JARVIS should allow the user to say:

> “Hey JARVIS, handle this.”

Then JARVIS should:

1. Understand the user’s goal.
2. Determine the required context.
3. Recall relevant history.
4. Break the goal into tasks.
5. Select appropriate agents and tools.
6. Explain the plan when useful.
7. Perform safe work.
8. Ask for approval before consequential actions.
9. Verify results.
10. Remember the outcome.
11. Continue unfinished work later.

### 2.3 Product personality

JARVIS should be:

- Calm.
- Respectful.
- Useful.
- Concise by default.
- Detailed when requested.
- Proactive but not intrusive.
- Confident when evidence is strong.
- Honest when uncertain.
- Context-aware.
- Warm without being theatrical.
- Professional without being robotic.

JARVIS MAY address the user as “sir” if the user enables that preference. It MUST NOT repeat the term unnaturally in every response.

### 2.4 Product boundaries

JARVIS MUST NOT:

- Grant itself permissions.
- Make irreversible decisions without approval.
- Treat a webpage, email, document, or screenshot as an authority that can override user policies.
- Claim a task is complete without evidence.
- Invent memories, dates, conversations, purchases, calls, or completed routines.
- Access cameras, microphones, screens, files, accounts, or locations without permission.
- Store sensitive data unnecessarily.
- Hide its actions from the user.
- Pretend to be human.
- Impersonate a real person.
- Clone a real person’s voice without authorization.
- Bypass operating-system or browser security controls.

***

## 3. Product Vision

### 3.1 Vision statement

Create a dependable personal AI operating system that understands the user across time, devices, tasks, projects, conversations, and routines while keeping the user in control of privacy and consequential actions.

### 3.2 Long-term vision

JARVIS should eventually become a trusted digital chief of staff that can:

- Manage personal and professional workflows.
- Research and explain complex topics.
- Write and revise documents.
- Build and fix software.
- Understand screens, cameras, documents, and calls.
- Coordinate specialized agents.
- Notice unfinished work.
- Identify useful opportunities.
- Prepare decisions.
- Execute approved actions.
- Maintain continuity across days and devices.

### 3.3 Success definition

JARVIS is successful when the user:

- Does not need to repeat context unnecessarily.
- Can find what was pending from previous days.
- Can trust dates and reminders.
- Can ask natural follow-up questions.
- Can delegate complex goals.
- Can see what JARVIS is doing.
- Can stop or revoke any capability.
- Feels assisted rather than controlled.
- Receives useful suggestions without unwanted surveillance.
- Can verify what happened and why.

***

## 4. Product Principles

### 4.1 User authority

The user owns the account, memory, permissions, and decisions.

### 4.2 Least privilege

Each agent and tool receives only the minimum access needed for its task.

### 4.3 Explicit approval

Consequential actions require approval for the exact action, target, amount, data, and timing.

### 4.4 Reversibility

When possible, JARVIS should prefer drafts, previews, branches, simulations, and reversible changes.

### 4.5 Truthful memory

JARVIS must distinguish:

- What the user said.
- What a tool reported.
- What JARVIS inferred.
- What is planned.
- What is scheduled.
- What is confirmed.
- What is completed.
- What is unknown.

### 4.6 Temporal continuity

JARVIS must understand that conversations occur on different dates and that unfinished work continues across days.

### 4.7 Privacy by design

Privacy must be implemented through architecture, not only through a system prompt.

### 4.8 Human-like, not human-deceptive

JARVIS may speak naturally and remember context, but it must not falsely claim to be human or imply human experiences it does not have.

### 4.9 Graceful uncertainty

When information is missing or ambiguous, JARVIS should ask a concise clarification question rather than guess.

### 4.10 Verification before confidence

JARVIS should validate work, cite sources where relevant, and report failures honestly.

### 4.11 Cloud-first practicality

The initial system uses cloud-hosted model APIs and Render hosting. Local model execution is not required for the first release.

### 4.12 Modular evolution

Providers, models, tools, interfaces, and agents must be replaceable without rewriting the entire platform.

***

## 5. Target Users

### 5.1 Primary user

The initial product is designed for one primary user who wants:

- Personal AI assistance.
- Voice interaction.
- Persistent memory.
- Productivity support.
- Business support.
- Coding help.
- Research.
- Communication assistance.
- Cross-device access.
- Privacy controls.

### 5.2 Future user types

Future releases MAY support:

- Family members.
- Assistants.
- Business teams.
- Employees.
- Guests.
- Organization administrators.
- Separate personal and work identities.

### 5.3 User profiles

Each user profile MUST support:

- Display name.
- Preferred form of address.
- Timezone.
- Locale.
- Preferred languages.
- Voice preference.
- Response-length preference.
- Formality preference.
- Notification preferences.
- Quiet hours.
- Memory preferences.
- Tool permissions.
- Connected devices.
- Personal/work context separation.

***

## 6. User Experience

### 6.1 Interaction surfaces

JARVIS SHOULD be accessible through:

- Web application.
- Responsive mobile web application.
- Desktop web application.
- Browser extension or companion.
- Mobile application in a later release.
- Voice interface.
- Hologram-inspired dashboard.
- Shared links to approved artifacts.
- Future wearable or display integrations.

### 6.2 Primary interaction modes

JARVIS MUST support:

- Text chat.
- Voice input.
- Voice output.
- Image upload.
- Camera session.
- Screen-share session.
- Document upload.
- Browser task.
- Tool execution.
- Background task status.
- Approval prompts.
- Scheduled notifications.

### 6.3 Conversation behavior

JARVIS should:

- Understand follow-up questions.
- Maintain session context.
- Retrieve relevant long-term context.
- Avoid repeating known information.
- Ask only necessary clarifying questions.
- Summarize complex plans.
- Confirm important assumptions.
- State when a request is ambiguous.
- Explain what it can and cannot access.

### 6.4 Response modes

JARVIS SHOULD support:

- Short answer.
- Detailed answer.
- Step-by-step mode.
- Executive briefing.
- Technical mode.
- Voice-friendly mode.
- Silent execution mode for safe background tasks.
- Approval mode.
- Debugging mode.
- Research mode.

### 6.5 Natural address

The user MAY configure:

- Name.
- Title.
- “Sir.”
- “Ma’am.”
- Neutral address.
- No form of address.

JARVIS MUST vary natural language and MUST NOT insert the title into every response unnaturally.

### 6.6 Contextual meal check-in example

If meal check-ins are enabled and local time is approximately 2 PM, JARVIS MAY say:

> “Have you eaten yet, sir?”

Rules:

- This behavior MUST be opt-in or explicitly enabled.
- It MUST use the user’s timezone.
- It MUST respect quiet hours.
- It MUST not be repeated continuously.
- It MUST not claim the user has or has not eaten.
- It MUST not provide medical advice merely because a meal was not reported.
- The user MUST be able to disable the behavior.

### 6.7 Proactive behavior boundaries

JARVIS MAY proactively:

- Remind about deadlines.
- Mention unfinished tasks.
- Notify about failures.
- Ask about scheduled routines.
- Prepare briefings.
- Surface relevant opportunities.
- Warn about unusual activity.
- Suggest next actions.

JARVIS MUST NOT proactively:

- Send messages without authorization.
- Make purchases.
- Call people.
- Publish content.
- Access sensors without permission.
- Repeatedly ask unanswered questions.
- Generate health anxiety.
- Interrupt during configured quiet hours.

***

## 7. System Architecture

### 7.1 Logical architecture

```text
User Interfaces
    ├── Web UI
    ├── Mobile UI
    ├── Voice UI
    ├── Browser companion
    └── Hologram dashboard
            │
            ▼
API Gateway and Session Layer
            │
            ├── Authentication
            ├── Session management
            ├── Rate limiting
            ├── Request validation
            └── WebSocket or realtime events
            │
            ▼
JARVIS Orchestrator
            │
            ├── Intent analysis
            ├── Context assembly
            ├── Planning
            ├── Agent delegation
            ├── Tool selection
            ├── Response generation
            └── Verification
            │
            ▼
Policy and Permission Broker
            │
            ├── Identity checks
            ├── Capability checks
            ├── Risk classification
            ├── Approval requirements
            ├── Data-scope enforcement
            └── Audit logging
            │
            ▼
Specialized Agents and Tools
            │
            ├── Memory
            ├── Tasks
            ├── Routines
            ├── Research
            ├── Coding
            ├── Browser
            ├── Vision
            ├── Calls
            ├── Writing
            ├── Business
            └── Communications
            │
            ▼
External Providers
            │
            ├── NVIDIA API
            ├── ElevenLabs API
            ├── Search providers
            ├── Calendar providers
            ├── Email providers
            ├── Telephony providers
            ├── Commerce providers
            └── Cloud storage
```

### 7.2 Deployment components

The initial deployment SHOULD include:

- Render web service.
- Render background worker if available.
- Render Cron Jobs.
- Persistent PostgreSQL-compatible database.
- External object storage for files.
- NVIDIA API integration.
- ElevenLabs API integration.
- Secure secret management.
- Error monitoring.
- Structured logging.

Render Cron Jobs use UTC cron expressions, so user-facing schedules MUST be converted between UTC and the user’s timezone [1].

### 7.3 Stateless web services

The web service SHOULD remain stateless where possible.

It MUST NOT rely on local filesystem persistence for:

- Memories.
- Tasks.
- Events.
- Audio.
- Images.
- User files.
- Approval records.
- Agent state.

Persistent data MUST be stored in a database or object-storage system.

### 7.4 Event-driven internal architecture

Internal operations SHOULD use typed events such as:

- `conversation.created`
- `message.received`
- `intent.classified`
- `memory.candidate.created`
- `memory.saved`
- `task.created`
- `task.updated`
- `routine.due`
- `approval.requested`
- `approval.granted`
- `approval.denied`
- `tool.started`
- `tool.completed`
- `tool.failed`
- `agent.started`
- `agent.completed`
- `notification.scheduled`
- `notification.sent`

### 7.5 Idempotency

All scheduled jobs and external action tools MUST support idempotency.

Repeated execution MUST NOT:

- Create duplicate reminders.
- Place duplicate orders.
- Send duplicate messages.
- Create duplicate events.
- Repeat a routine check-in for the same occurrence.
- Duplicate database records.

***

## 8. Agent Architecture

### 8.1 Agent model

JARVIS is an orchestrator coordinating specialized agents.

Each agent MUST have:

- Defined purpose.
- Defined tools.
- Defined data scopes.
- Defined output schema.
- Defined risk profile.
- Defined escalation rules.
- Defined timeout.
- Defined retry policy.
- Defined audit behavior.

### 8.2 Main orchestrator agent

Responsibilities:

- Understand user intent.
- Retrieve relevant context.
- Choose the appropriate workflow.
- Delegate to specialized agents.
- Track progress.
- Ask clarifying questions.
- Request approvals.
- Verify results.
- Summarize outcomes.
- Save durable information.

The orchestrator MUST NOT bypass the permission broker.

### 8.3 Memory agent

Responsibilities:

- Extract memory candidates.
- Classify memory type.
- Detect conflicts.
- Apply user scope.
- Store provenance.
- Retrieve relevant memories.
- Apply expiration.
- Handle forget and correction requests.
- Prevent sensitive-memory leakage.

### 8.4 Date and time agent

Responsibilities:

- Parse relative dates.
- Parse recurring schedules.
- Resolve timezone.
- Detect ambiguity.
- Convert user language to exact timestamps.
- Compute next occurrence.
- Explain date interpretation.

### 8.5 Task agent

Responsibilities:

- Create tasks.
- Update tasks.
- Track status.
- Detect blockers.
- Identify stale tasks.
- Suggest next actions.
- Produce pending-work summaries.
- Link tasks to conversations and projects.

### 8.6 Routine agent

Responsibilities:

- Create recurring routines.
- Create one-time events.
- Generate due occurrences.
- Check notification policy.
- Prevent duplicate check-ins.
- Record confirmations.
- Distinguish plans from completed history.

### 8.7 Research agent

Responsibilities:

- Search approved sources.
- Compare results.
- Extract facts.
- Cite sources.
- Identify uncertainty.
- Monitor tracked topics.
- Produce research briefs.

### 8.8 Coding agent

Responsibilities:

- Understand repositories.
- Plan changes.
- Write code.
- Run tests.
- Analyze errors.
- Create diffs.
- Explain changes.
- Work in isolated branches or workspaces.
- Request approval before deployment or destructive changes.

### 8.9 Browser/computer agent

Responsibilities:

- Navigate approved sites.
- Read page content.
- Fill forms.
- Compare products.
- Prepare checkout.
- Operate approved applications.
- Produce screenshots or recordings.
- Stop before consequential actions unless approved.

Web content MUST be treated as untrusted input and MUST NOT grant permissions.

### 8.10 Vision agent

Responsibilities:

- Analyze approved images.
- Analyze camera frames.
- Analyze documents.
- Analyze screen captures.
- Identify visual objects.
- Explain charts and interfaces.
- Respect privacy restrictions.
- Delete temporary data according to retention policy.

### 8.11 Voice agent

Responsibilities:

- Receive speech input.
- Handle interruption.
- Produce natural speech.
- Select voice profile.
- Respect language and voice preferences.
- Report external voice processing.
- Avoid storing raw audio unnecessarily.

### 8.12 Communication agent

Responsibilities:

- Draft email.
- Draft messages.
- Prepare calls.
- Summarize conversations.
- Extract commitments.
- Schedule follow-ups.
- Never send or call without required approval.

### 8.13 Business agent

Responsibilities:

- Analyze business data.
- Identify leads.
- Research competitors.
- Suggest growth ideas.
- Draft outreach.
- Prepare reports.
- Score opportunities.
- Never send bulk outreach or spend budget without approval.

### 8.14 Safety agent

Responsibilities:

- Evaluate risk.
- Detect prompt injection.
- Enforce tool policies.
- Detect sensitive data.
- Require approval.
- Block prohibited actions.
- Audit tool calls.
- Escalate uncertainty.

***

## 9. Model Strategy

### 9.1 Model provider

NVIDIA APIs are the initial model provider.

NVIDIA NIM exposes model services through standardized APIs and supports hosted model endpoints and portable inference services [2]. The implementation MUST use a provider abstraction so the application is not permanently coupled to one model.

### 9.2 Model router

The router SHOULD choose a model based on:

- Task category.
- Required modality.
- Reasoning difficulty.
- Latency.
- Context length.
- Privacy classification.
- Provider availability.
- Rate limits.
- Cost or quota.
- User preference.

### 9.3 Model classes

The system SHOULD define logical model roles:

- `fast_chat`
- `reasoning`
- `coding`
- `vision`
- `document`
- `voice_understanding`
- `safety`
- `summarization`
- `classification`
- `embedding`

The specific provider model IDs MUST be configuration-driven.

### 9.4 Model routing rules

Examples:

```text
Simple greeting → fast_chat
Complex planning → reasoning
Code generation → coding
Screenshot analysis → vision
Document extraction → document
Risk classification → safety
Conversation summarization → summarization
Memory retrieval → embedding + retrieval
```

### 9.5 Fallback behavior

If the preferred model fails:

1. Retry according to policy.
2. Try an approved fallback model.
3. Reduce task scope if appropriate.
4. Inform the user if quality or capability changes.
5. Never silently route sensitive data to an unapproved provider.

### 9.6 Model output requirements

Models SHOULD produce structured output for:

- Intent.
- Task plans.
- Memory candidates.
- Tool calls.
- Approval requests.
- Risk classification.
- Date interpretation.
- Routine interpretation.
- Completion claims.

Free-form model output MUST NOT be used as the sole authorization mechanism.

### 9.7 Provider observability

Record:

- Provider.
- Model.
- Request ID.
- Latency.
- Token or usage metadata where available.
- Error type.
- Retry count.
- User-visible result.
- Privacy classification.

Do not store sensitive prompts or outputs unnecessarily.

***

## 10. Voice System

### 10.1 Voice provider

ElevenLabs is the initial speech provider.

The ElevenLabs API supports text-to-speech generation using a selected voice and per-request voice settings [3][4]. Voice settings include properties such as speed, stability, similarity, and style [5].

### 10.2 Voice profiles

JARVIS MUST support configurable voice profiles:

- Indian English male.
- Indian English female.
- Neutral English male.
- Neutral English female.
- Hindi voice where supported.
- Telugu voice where supported.
- Custom future profiles.

Voice profile data:

- Profile ID.
- Display name.
- Provider.
- Voice ID.
- Language.
- Locale.
- Gender presentation.
- Tone.
- Speed.
- Stability.
- Style.
- User visibility.
- Consent metadata if custom voice.

### 10.3 Voice selection

The user MAY say:

- “Use the male voice.”
- “Use the female voice.”
- “Speak slower.”
- “Use Indian English.”
- “Use Hindi.”
- “Use Telugu.”
- “Use the professional voice.”
- “Use the casual voice.”

### 10.4 Voice privacy

The system MUST:

- Keep ElevenLabs API keys server-side.
- Avoid retaining generated audio unless needed.
- Disclose when user content is sent for voice generation.
- Never clone a real person without documented permission.
- Provide a voice reset.
- Log voice-provider usage without storing full sensitive text unnecessarily.

### 10.5 Natural speech

JARVIS SHOULD:

- Use short sentences for voice.
- Avoid excessive lists unless requested.
- Handle interruptions.
- Confirm numbers and dates clearly.
- Repeat critical totals before approval.
- Avoid speaking private data aloud in public mode.

### 10.6 Voice safety

Before speaking sensitive information, JARVIS SHOULD consider:

- Whether the user is authenticated.
- Whether the device is private.
- Whether the user has enabled private voice mode.
- Whether the response contains financial, health, identity, or security data.

***

## 11. Conversation and Context System

### 11.1 Context layers

Every response SHOULD be generated from layered context:

1. Current user message.
2. Current session.
3. Recent conversation summary.
4. Relevant long-term memories.
5. Active tasks and projects.
6. Current date and time.
7. Due events and routines.
8. User preferences.
9. Device context.
10. Permission state.
11. Relevant tool results.
12. Safety policy.

### 11.2 Context budget

The system MUST avoid sending all memory to every model request.

It SHOULD retrieve context based on:

- Semantic relevance.
- Recency.
- User scope.
- Project scope.
- Time relevance.
- Importance.
- Sensitivity.
- Current intent.

### 11.3 Context brief

Before response generation, the orchestrator SHOULD create an internal structured brief:

```json
{
  "current_time": "2026-10-18T14:00:00+05:30",
  "user_timezone": "Asia/Kolkata",
  "relevant_memories": [],
  "pending_tasks": [],
  "due_routines": [],
  "active_projects": [],
  "permissions": [],
  "risk_level": "low",
  "response_style": "natural_concise"
}
```

### 11.4 Conversation continuity

JARVIS MUST be able to understand:

- “Continue yesterday’s work.”
- “What was pending?”
- “What did we decide?”
- “Use the same style as last time.”
- “What did I ask you to remember?”
- “When is that due?”
- “Did I already send it?”
- “What happened with that order?”

### 11.5 Clarification strategy

JARVIS SHOULD ask one focused question at a time.

Example:

> “Which project do you mean: the website or the mobile app?”

It SHOULD NOT ask the user to repeat information already available in memory unless the existing information is ambiguous or stale.

***

## 12. Memory and Learning

### 12.1 Memory definition

Memory is persisted information that helps JARVIS provide continuity across conversations and time.

Memory is not identical to:

- Raw chat history.
- Temporary context.
- Tool output.
- User profile.
- Task state.
- Calendar event.

### 12.2 Memory classes

The system MUST distinguish:

- Semantic memory: stable facts and preferences.
- Episodic memory: what happened in a specific interaction.
- Procedural memory: how the user prefers work performed.
- Task memory: unfinished or completed work.
- Temporal memory: events and dates.
- Relationship memory: people and entities.
- Sensitive memory: health, finance, identity, or private content.
- Device memory: device capabilities and permissions.

### 12.3 Memory candidate extraction

After a conversation, JARVIS MAY extract candidates such as:

- “Remember I prefer concise answers.”
- “My business uses WhatsApp for customer support.”
- “I am working on a website.”
- “Remind me next Friday.”
- “I do not want cloud processing for private documents.”

The system MUST NOT save candidates automatically when:

- The user explicitly requests no memory.
- The content is temporary.
- The content is uncertain.
- The content is sensitive and lacks permission.
- The content is merely conversational filler.

### 12.4 Memory schema

Each memory SHOULD include:

```text
id
user_id
type
content
structured_value
source_type
source_reference
created_at
updated_at
valid_from
valid_until
confidence
importance
sensitivity
privacy_scope
project_id
embedding
status
```

### 12.5 Memory provenance

JARVIS MUST know whether information came from:

- User statement.
- Calendar.
- Email.
- Tool result.
- Uploaded document.
- Agent inference.
- System configuration.
- External API.

Responses SHOULD distinguish facts from inferences.

### 12.6 Memory conflict resolution

If a new memory conflicts with an old one:

1. Compare timestamps.
2. Compare source reliability.
3. Ask for clarification if needed.
4. Preserve history rather than silently deleting it.
5. Mark old information as superseded if appropriate.
6. Use the newest confirmed information for current responses.

### 12.7 Memory expiry

Memory MAY have:

- No expiry.
- Session expiry.
- Date expiry.
- Project expiry.
- User-triggered deletion.
- Automatic retention expiry.

### 12.8 User controls

The user MUST be able to say:

- “What do you remember about me?”
- “Remember this.”
- “Forget that.”
- “Correct that.”
- “Do not save this.”
- “Delete everything about this project.”
- “Make this private.”
- “Remember this only until Friday.”
- “Do not use my business memory in personal conversations.”

### 12.9 Memory retrieval

Memory retrieval MUST be scoped by:

- User.
- Agent.
- Project.
- Privacy level.
- Current task.
- Permission.
- Relevance.

No user may retrieve another user’s memory.

### 12.10 Learning behavior

JARVIS SHOULD learn preferences gradually, but it MUST distinguish:

- Explicit preference.
- Repeated observed preference.
- Temporary request.
- Inferred preference.
- Uncertain preference.

JARVIS SHOULD ask before turning repeated behavior into a permanent preference.

***

## 13. Time, Date, and Temporal Reasoning

### 13.1 Timezone

Initial user timezone:

```text
Asia/Kolkata
```

The system MUST store timestamps in UTC or an equivalent normalized representation while preserving the original timezone where relevant.

### 13.2 Relative date interpretation

JARVIS MUST understand:

- Today.
- Yesterday.
- Tomorrow.
- This morning.
- This afternoon.
- Tonight.
- Next Monday.
- Last Friday.
- In two hours.
- In three days.
- Next month.
- By month-end.
- After the meeting.

### 13.3 Ambiguous dates

If a phrase has multiple interpretations, JARVIS MUST clarify.

Example:

> “Remind me next Monday.”

Possible response:

> “Do you mean Monday, October 19, at what time in IST?”

### 13.4 Date storage

Every event SHOULD store:

- Local date.
- Local time.
- UTC timestamp.
- Original timezone.
- Recurrence rule if any.
- Natural-language source.
- Resolution confidence.

### 13.5 Temporal language

JARVIS SHOULD use natural relative language when appropriate:

- “Yesterday.”
- “Tomorrow.”
- “This Monday.”
- “Three days ago.”

For important actions, JARVIS SHOULD also provide the exact date:

> “Tomorrow, Monday, October 19, at 9 AM IST.”

### 13.6 Historical accuracy

JARVIS MUST NOT claim:

- A task was completed when it was only planned.
- A routine occurred because it was scheduled.
- A reminder was delivered when delivery failed.
- A fasting event happened when it was not confirmed.
- A message was sent when the provider did not confirm success.

***

## 14. Tasks, Projects, and Pending Work

### 14.1 Task model

Each task SHOULD include:

```text
id
user_id
title
description
status
priority
created_at
started_at
last_updated_at
due_at
completed_at
blocked_reason
next_action
project_id
source_conversation_id
assigned_agent
approval_id
external_reference
```

### 14.2 Task statuses

Supported statuses:

- Inbox.
- Planned.
- In progress.
- Blocked.
- Waiting for user.
- Waiting for approval.
- Completed.
- Cancelled.
- Archived.

### 14.3 Pending-work query

When the user asks:

> “What is pending?”

JARVIS SHOULD retrieve:

- Unfinished tasks.
- Blocked tasks.
- Waiting approvals.
- Failed agent runs.
- Upcoming deadlines.
- Tasks updated yesterday.
- Tasks related to current projects.
- Open commitments.

### 14.4 Yesterday continuity

When the user asks:

> “What was pending from yesterday?”

JARVIS SHOULD search:

- Tasks last updated yesterday.
- Tasks created yesterday.
- Conversations yesterday.
- Agent runs yesterday.
- Open approvals from yesterday.
- Events that were not confirmed.
- Failed work from yesterday.

### 14.5 Next action

Every active task SHOULD have a next action where possible.

Example:

```text
Task: Fix checkout bug
Status: Blocked
Blocker: Missing payment API key
Next action: Ask user for the key or configure test credentials
```

### 14.6 Task completion

A task may be marked complete only when:

- The user confirms completion.
- A trusted external tool confirms success.
- The agent verifies the result.
- A workflow explicitly defines completion criteria.

### 14.7 Stale tasks

JARVIS MAY detect tasks that have been inactive for a configurable period and ask:

> “This task has been waiting for 10 days. Do you want to continue, reschedule, delegate, or archive it?”

It MUST NOT silently delete the task.

***

## 15. Events, Routines, and Personal Habits

### 15.1 Event types

The system MUST distinguish:

- One-time planned event.
- One-time confirmed event.
- One-time completed event.
- Recurring routine.
- Routine occurrence.
- Check-in.
- Confirmation.
- Missed occurrence.
- Cancelled occurrence.

### 15.2 Recurring routine example

User says:

> “Every Monday I fast.”

JARVIS creates:

```text
type: recurring_routine
title: fasting
recurrence: weekly
weekday: Monday
timezone: Asia/Kolkata
status: active
check_in_frequency: once_per_occurrence
```

On Monday, JARVIS MAY say:

> “How is your fasting going today?”

It MUST:

- Check only on Monday.
- Check at most once for that occurrence.
- Respect quiet hours.
- Not claim fasting was completed.
- Wait for user confirmation.

### 15.3 One-time event example

User says:

> “I am fasting only today.”

JARVIS creates:

```text
type: one_time_event
title: fasting
date: current local date
recurrence: none
status: planned
```

It MUST NOT:

- Create a recurring routine.
- Ask about fasting tomorrow.
- Ask every day.
- Mark it completed without confirmation.

### 15.4 Confirmed event example

User says:

> “I fasted today.”

JARVIS creates:

```text
type: historical_event
title: fasting
date: current local date
status: completed
confirmation: user_confirmed
```

### 15.5 Future plan example

User says:

> “I will fast today.”

JARVIS creates:

```text
type: one_time_event
title: fasting
date: current local date
status: planned
```

It MUST NOT be represented as completed.

### 15.6 Last fasting query

If the user asks:

> “When was my last fasting?”

JARVIS MUST search confirmed historical events first.

It SHOULD respond:

> “Your last confirmed fasting day was Monday, October 12. You also have a recurring Monday fasting routine, but this week’s occurrence has not been confirmed.”

If no confirmed history exists:

> “I have a fasting plan for today, but I do not have a confirmed completed fasting day in memory.”

### 15.7 Generalization

The same temporal model MUST work for:

- Exercise.
- Medication reminders, without diagnosing.
- Study routines.
- Prayer routines.
- Work shifts.
- Weekly reviews.
- Water reminders.
- Personal habits.
- Meetings.
- Recurring bills.
- Cleaning schedules.
- Business follow-ups.

### 15.8 Routine schema

Each routine SHOULD include:

```text
id
user_id
title
description
recurrence_rule
timezone
start_date
end_date
active
check_in_policy
quiet_hours_policy
last_check_in_at
last_confirmed_at
next_due_at
created_from_message
created_at
updated_at
```

### 15.9 Notification deduplication

A routine occurrence MUST have a unique identity, for example:

```text
routine_id + occurrence_date + check_in_type
```

The scheduler MUST use this identity to prevent duplicate questions.

***

## 16. Proactive Intelligence

### 16.1 Morning briefing

JARVIS MAY provide:

- Date and local time.
- Weather if enabled.
- Calendar.
- Deadlines.
- Pending tasks.
- Important notifications.
- Routine check-ins.
- Failed agent work.
- Suggested priorities.

### 16.2 Evening briefing

JARVIS MAY provide:

- Completed tasks.
- Unfinished tasks.
- Blockers.
- Upcoming deadlines.
- Decisions made.
- Pending approvals.
- Tomorrow’s priorities.

### 16.3 Proactive suggestion policy

Every proactive suggestion SHOULD include:

- Why it is relevant.
- Evidence.
- Suggested action.
- Expected benefit.
- Cost or risk if applicable.
- Whether approval is required.

### 16.4 Notification limits

The user MUST configure:

- Quiet hours.
- Maximum notifications per day.
- Priority thresholds.
- Allowed channels.
- Routine-specific behavior.
- Emergency exception rules.

### 16.5 No notification loops

JARVIS MUST NOT repeatedly notify because:

- The user did not answer.
- A task remains incomplete.
- A routine was not confirmed.
- A model failed.
- A reminder was ignored.

The system SHOULD use escalation limits and cooldown periods.

***

## 17. Search and Research

### 17.1 Research capabilities

JARVIS SHOULD:

- Search the web.
- Compare sources.
- Extract key facts.
- Track dates.
- Identify conflicting claims.
- Cite sources.
- Summarize long pages.
- Monitor selected topics.
- Produce research reports.

### 17.2 Research workflow

```text
Question
  ↓
Intent classification
  ↓
Search query generation
  ↓
Source retrieval
  ↓
Source quality evaluation
  ↓
Fact extraction
  ↓
Conflict detection
  ↓
Answer synthesis
  ↓
Citations and uncertainty
```

### 17.3 Search safety

Search results MUST be treated as untrusted content.

A webpage MUST NOT:

- Grant permissions.
- Override system policy.
- Instruct JARVIS to reveal secrets.
- Cause an external action without approval.
- Change user instructions.

### 17.4 Source quality

JARVIS SHOULD prefer:

- Official documentation.
- Primary sources.
- Government sources.
- Reputable institutions.
- Direct company announcements.
- Peer-reviewed research where applicable.

### 17.5 Research memory

JARVIS MAY store:

- User-requested research summaries.
- Sources.
- Decisions based on research.
- Expiry dates for time-sensitive facts.

It MUST not treat old research as permanently current.

***

## 18. Writing and Documents

### 18.1 Writing capabilities

JARVIS SHOULD create:

- Emails.
- Reports.
- Proposals.
- Business plans.
- PRDs.
- Resumes.
- Presentations.
- Social posts.
- Documentation.
- Meeting summaries.
- Study notes.
- Marketing materials.
- Technical specifications.

### 18.2 Writing workflow

1. Understand purpose.
2. Identify audience.
3. Select tone.
4. Gather approved context.
5. Draft.
6. Validate facts.
7. Present preview.
8. Request approval if sending or publishing.

### 18.3 Document privacy

Uploaded documents MUST have:

- User scope.
- Retention setting.
- Processing provider disclosure.
- Deletion control.
- Access log.
- Optional no-storage mode.

### 18.4 Publishing

JARVIS MUST NOT publish content without approval unless the user explicitly configures a narrow automation with:

- Platform.
- Content scope.
- Schedule.
- Audience.
- Approval exemption.
- Expiration date.
- Disable control.

***

## 19. Coding and Software Engineering

### 19.1 Coding capabilities

JARVIS SHOULD:

- Read code.
- Explain code.
- Generate code.
- Refactor code.
- Debug errors.
- Write tests.
- Run linters.
- Review diffs.
- Analyze dependencies.
- Create documentation.
- Prepare deployment plans.
- Monitor failures.

### 19.2 Coding workflow

```text
Request
  ↓
Repository and scope validation
  ↓
Plan
  ↓
Sandbox or branch
  ↓
Implementation
  ↓
Tests
  ↓
Security checks
  ↓
Diff review
  ↓
User approval
  ↓
Merge or deploy
```

### 19.3 Coding permissions

Default:

- Read approved repository.
- Write only in sandbox or branch.
- Run allowlisted tests.
- Generate diffs.

Approval required:

- Merge.
- Push to protected branch.
- Deploy.
- Modify secrets.
- Change infrastructure.
- Delete files.
- Run arbitrary shell commands.
- Access a new network destination.

### 19.4 Code execution

Code execution MUST be isolated where possible.

The system SHOULD use:

- Sandboxed workspace.
- Resource limits.
- Network restrictions.
- Timeouts.
- Dependency allowlists.
- Artifact scanning.
- Secret redaction.
- Reproducible test environments.

### 19.5 Deployment

Production deployment MUST require:

- Passing tests.
- Security checks.
- Diff preview.
- Environment confirmation.
- User approval.
- Rollback plan.
- Deployment log.

***

## 20. Browser and Computer Use

### 20.1 Browser capabilities

JARVIS SHOULD:

- Open approved pages.
- Search.
- Read.
- Fill forms.
- Compare products.
- Prepare checkout.
- Download approved files.
- Create screenshots.
- Navigate dashboards.
- Operate web applications.

### 20.2 Computer capabilities

Future desktop integration MAY support:

- Screen reading.
- Mouse control.
- Keyboard input.
- Application launching.
- File selection.
- Window management.
- UI interaction.

### 20.3 Computer-use safety

JARVIS MUST:

- Treat screen content as untrusted.
- Keep a visible active-control indicator.
- Ask before entering sensitive data.
- Ask before submitting consequential forms.
- Stop before purchase confirmation.
- Stop before sending messages.
- Stop before deleting data.
- Stop before changing accounts or permissions.
- Log actions.

### 20.4 Shopping workflow

For:

> “Order this for me.”

JARVIS MUST:

1. Identify the product.
2. Confirm variant and quantity.
3. Compare approved sellers.
4. Check price.
5. Check delivery.
6. Check returns and warranty.
7. Prepare checkout.
8. Show final total.
9. Show delivery address.
10. Show payment method without exposing full credentials.
11. Request explicit approval.
12. Execute only after approval.
13. Verify order confirmation.
14. Store order details securely.
15. Provide cancellation or return information.

JARVIS MUST NOT place an order based on vague approval.

***

## 21. Camera, Vision, and Screen Sharing

### 21.1 Camera session

When the user says:

> “Access my camera and tell me what you see.”

JARVIS MUST:

1. Explain that camera access is required.
2. Request permission.
3. Identify the device and camera.
4. Show visible camera-active status.
5. Process only the approved session.
6. Explain whether data leaves the device.
7. Avoid storing raw frames unless explicitly requested.
8. Stop the session when the task ends.
9. Record the access event in the audit log.

### 21.2 Camera modes

Supported modes:

- Single frame.
- Short session.
- Continuous session.
- Disabled.

Continuous mode MUST require separate explicit activation.

### 21.3 Screen sharing

When the user asks JARVIS to inspect the screen, it MUST:

- Request screen permission.
- Indicate the active window or display.
- Warn about visible private content.
- Avoid capturing unrelated screens.
- Stop when the session ends.
- Not store screenshots by default.

### 21.4 Vision questions

Examples:

- “What are you seeing?”
- “Read this document.”
- “Why is this error appearing?”
- “What is on my desk?”
- “Explain this chart.”
- “Compare these two products.”
- “Find the button I need to press.”

JARVIS MUST distinguish observation from inference.

### 21.5 Sensitive visual content

The system SHOULD detect or warn about:

- Passwords.
- Payment information.
- Identity documents.
- Private messages.
- Health records.
- Secret keys.
- Faces of bystanders.
- Confidential business information.

***

## 22. Phone Calls and Communication

### 22.1 Call capabilities

JARVIS MAY support:

- Call screening.
- Caller identification.
- Call summaries.
- Call transcription.
- Appointment scheduling.
- Outbound calls.
- Follow-up task creation.
- Live private suggestions.
- Human handoff.

### 22.2 Call permissions

Before an outbound call, JARVIS MUST show:

- Recipient.
- Purpose.
- Information it may share.
- Whether recording is enabled.
- Whether transcription is enabled.
- Allowed outcomes.
- Escalation behavior.

### 22.3 Call identity

JARVIS MUST:

- Identify itself as an AI when required.
- Not impersonate the user.
- Not make unauthorized promises.
- Not disclose private information.
- Not manipulate a caller.
- Respect call recording laws and consent requirements.

### 22.4 Call summary

After a call, JARVIS SHOULD produce:

- Participants.
- Time.
- Main points.
- Commitments.
- Deadlines.
- Follow-up tasks.
- Unresolved questions.
- Recording retention status.

***

## 23. Business and Productivity

### 23.1 Business capabilities

JARVIS SHOULD:

- Analyze revenue.
- Analyze expenses.
- Track leads.
- Monitor customer follow-ups.
- Research competitors.
- Identify buying signals.
- Draft outreach.
- Analyze website performance.
- Suggest growth opportunities.
- Prepare proposals.
- Draft reports.
- Track projects.
- Identify operational bottlenecks.

### 23.2 Opportunity recommendations

Every recommendation SHOULD include:

- Opportunity.
- Evidence.
- Expected benefit.
- Estimated effort.
- Cost.
- Risk.
- Confidence.
- Recommended next step.
- Approval requirements.

### 23.3 Lead workflow

```text
Define ideal customer
  ↓
Find approved sources
  ↓
Identify suitable prospects
  ↓
Detect buying signals
  ↓
Research contacts
  ↓
Score leads
  ↓
Draft outreach
  ↓
User review
  ↓
Send with approval
  ↓
Track response
```

### 23.4 Outreach safety

JARVIS MUST NOT:

- Conduct uncontrolled mass messaging.
- Use unauthorized personal data.
- Misrepresent identity.
- Ignore opt-outs.
- Send messages without appropriate approval.
- Store unnecessary sensitive prospect data.

***

## 24. Orders, Purchases, and Bookings

### 24.1 Supported future actions

JARVIS MAY prepare:

- Product orders.
- Food orders.
- Travel bookings.
- Appointment bookings.
- Ticket purchases.
- Subscription changes.
- Bill payments.

### 24.2 Approval policy

Every purchase approval MUST identify:

- Item or service.
- Seller or provider.
- Quantity.
- Price.
- Taxes.
- Fees.
- Delivery or appointment time.
- Address or destination.
- Payment method.
- Cancellation terms.

### 24.3 Payment data

JARVIS MUST NOT store full payment credentials.

It SHOULD use:

- Merchant checkout.
- Tokenized payment provider.
- User biometric confirmation.
- Secure payment approval flow.

### 24.4 Duplicate prevention

The purchase workflow MUST use an idempotency key and verify the order result before retrying.

***

## 25. Multi-Agent Orchestration

### 25.1 Delegation

The orchestrator MAY delegate tasks when:

- The task requires specialist knowledge.
- Parallel work reduces latency.
- The task has separable components.
- A specialist has narrower data access.

### 25.2 Delegation record

Every delegated task SHOULD include:

- Parent task ID.
- Child agent ID.
- Goal.
- Input scope.
- Data permissions.
- Tools allowed.
- Expected output.
- Deadline.
- Risk level.
- Status.
- Result.
- Failure reason.

### 25.3 Parallel work

Parallel agents MAY perform:

- Market research.
- Competitor comparison.
- Code review.
- Document drafting.
- Test generation.
- Data analysis.

The orchestrator MUST merge results and detect conflicts.

### 25.4 Agent communication

Agents SHOULD communicate through structured messages rather than unbounded raw transcripts.

### 25.5 Agent failure

If an agent fails:

- Retry only when safe.
- Avoid duplicate external actions.
- Record the failure.
- Explain the blocker.
- Offer a next step.
- Escalate to the user when needed.

***

## 26. Permissions and Approval System

### 26.1 Permission architecture

Permissions MUST be enforced outside the language model.

The model may propose:

```json
{
  "tool": "send_email",
  "recipient": "example@example.com",
  "subject": "Draft",
  "body": "Message",
  "risk": "high"
}
```

The policy broker decides whether this is allowed.

### 26.2 Capability categories

Capabilities include:

- Read conversation.
- Read memory.
- Write memory.
- Read tasks.
- Write tasks.
- Read calendar.
- Create calendar event.
- Read email.
- Draft email.
- Send email.
- Read files.
- Write files.
- Delete files.
- Access camera.
- Access microphone.
- Access screen.
- Make call.
- Send message.
- Search web.
- Browse website.
- Purchase item.
- Spend money.
- Deploy code.
- Change permissions.

### 26.3 Permission levels

- Denied.
- Ask every time.
- Allowed for session.
- Allowed for specific tool.
- Allowed for specific resource.
- Allowed until expiry.
- Allowed under a narrow automation rule.

### 26.4 Risk classes

#### Low risk

- Answer question.
- Search web.
- Summarize approved content.
- Draft text.
- Analyze selected image.
- Create private note.
- Run sandbox tests.

#### Medium risk

- Modify user files.
- Create calendar events.
- Update CRM.
- Upload a document.
- Access screen session.
- Access camera session.
- Access microphone session.

#### High risk

- Send messages.
- Make calls.
- Publish content.
- Purchase.
- Spend money.
- Delete data.
- Change passwords.
- Change permissions.
- Deploy production code.
- Unlock devices.

### 26.5 Approval object

Each approval SHOULD include:

```text
id
user_id
requested_action
tool_name
arguments_hash
display_summary
risk_level
data_scope
created_at
expires_at
status
approved_by
approval_method
execution_result
```

### 26.6 Approval integrity

Approval MUST be bound to:

- Exact tool.
- Exact arguments.
- Exact recipient.
- Exact amount.
- Exact scope.
- Expiration time.

Changing any material parameter MUST require a new approval.

### 26.7 Emergency controls

The user MUST be able to:

- Stop current agent run.
- Revoke current session permissions.
- Revoke all device sessions.
- Disable voice.
- Disable camera.
- Disable screen access.
- Disable all external actions.
- Delete pending approvals.
- Lock the account.

***

## 27. Privacy and Security

### 27.1 Security principles

The system MUST follow:

- Least privilege.
- Deny by default for sensitive tools.
- User data isolation.
- Secure secret storage.
- Encryption in transit.
- Encryption at rest where supported.
- Minimal retention.
- Auditability.
- Explicit consent.
- Revocation.

OWASP recommends per-tool permission scoping, separation of read and write capabilities, and human approval for irreversible actions [6].

### 27.2 API key security

API keys MUST:

- Exist only on the server.
- Be stored as managed secrets.
- Never appear in frontend code.
- Never be written to logs.
- Be rotated periodically.
- Be scoped where provider support exists.

### 27.3 Data classifications

Data SHOULD be classified as:

- Public.
- Internal.
- Personal.
- Sensitive personal.
- Financial.
- Health-related.
- Authentication secret.
- Business confidential.
- Highly restricted.

### 27.4 Retention

The system MUST define retention for:

- Chat messages.
- Audio.
- Images.
- Screen captures.
- Documents.
- Tool outputs.
- Memory.
- Audit logs.
- Call transcripts.
- Approval records.

### 27.5 Deletion

Users MUST be able to request:

- Delete one message.
- Delete one memory.
- Delete a project.
- Delete all voice data.
- Delete all uploaded files.
- Delete account data.

Deletion MUST be auditable and should propagate to dependent indexes and embeddings.

### 27.6 Prompt injection defense

The system MUST treat external content as untrusted.

Defenses SHOULD include:

- Separate data from instructions.
- Tool argument validation.
- Permission checks after model output.
- Allowlists.
- Content scanning.
- Confirmation for risky actions.
- Isolation of browser sessions.
- No secret exposure to untrusted page content.

### 27.7 Authentication

The system SHOULD support:

- Secure login.
- Email verification.
- Strong session management.
- Device/session list.
- Session revocation.
- Optional MFA.
- Optional passkey or biometric confirmation through supported clients.

### 27.8 Audit logs

Audit events SHOULD include:

- User.
- Device.
- Timestamp.
- Action.
- Tool.
- Data scope.
- Approval.
- Result.
- Error.
- IP or session metadata where appropriate.

***

## 28. Hologram-Inspired User Interface

### 28.1 UI objective

The interface should feel cinematic and futuristic while remaining usable, accessible, and informative.

### 28.2 Visual system

Possible visual elements:

- Dark background.
- Cyan and blue accent colors.
- Glowing orbital rings.
- Animated central core.
- Voice waveform.
- Floating cards.
- Radial action menu.
- Agent activity graph.
- Task timeline.
- Device network map.
- Permission indicators.
- Approval panels.
- GPU, CPU, latency, and API usage cards.
- Camera and screen status indicators.

### 28.3 UI modes

- Conversation mode.
- Voice mode.
- Command-center mode.
- Approval mode.
- Agent-monitoring mode.
- Task timeline mode.
- Memory mode.
- Device mode.
- Privacy mode.
- Research mode.
- Coding mode.

### 28.4 Hologram constraints

The initial UI is a rendered 2D interface with hologram-style visual design.

Future display targets MAY include:

- Transparent screen.
- Projector.
- Pepper’s Ghost display.
- Large wall display.
- 3D visualization hardware.

The backend MUST remain independent of the physical display.

### 28.5 Accessibility

The UI MUST support:

- Keyboard navigation.
- Screen readers where practical.
- High contrast mode.
- Reduced motion mode.
- Text-only mode.
- Voice-only mode.
- Color-blind-safe status indicators.
- Clear permission states.

### 28.6 Activity visualization

The user SHOULD see:

- Active agents.
- Current task.
- Tools being called.
- Waiting approvals.
- Completed steps.
- Failed steps.
- Data leaving the system.
- Camera/microphone/screen status.

***

## 29. Cross-Device and Wi-Fi Context

### 29.1 Device registry

Each device SHOULD have:

- Device ID.
- User ID.
- Device type.
- Name.
- OS.
- Capabilities.
- Last active time.
- Network status.
- Permissions.
- Session token.
- Revocation state.

### 29.2 Device capabilities

Capabilities include:

- Microphone.
- Camera.
- Screen capture.
- Speaker.
- Location.
- Files.
- Browser.
- Notifications.
- Phone.
- Bluetooth.
- Display.

### 29.3 Device selection

JARVIS MAY ask:

> “Which camera should I use: your phone or laptop?”

It MUST NOT choose a sensitive device silently if the user’s intent is ambiguous.

### 29.4 Wi-Fi awareness

Future Wi-Fi-aware features MAY include:

- Detecting trusted network.
- Adjusting privacy policy.
- Choosing a nearby device.
- Displaying on an available screen.
- Disabling sensitive speech in public networks.
- Showing device presence.

Wi-Fi presence MUST NOT be treated as exact physical location unless separately authorized.

### 29.5 Device handoff

The user SHOULD be able to start on one device and continue on another.

Example:

> “Continue the report I started on my laptop.”

JARVIS retrieves the task and session summary, not necessarily the full private screen content.

***

## 30. External Integrations

### 30.1 NVIDIA integration

The NVIDIA integration MUST support:

- Server-side API calls.
- Configurable model IDs.
- Model discovery where supported.
- Request timeouts.
- Retries.
- Error normalization.
- Usage logging.
- Provider fallback abstraction.
- Vision requests where supported.
- Structured tool-call outputs where supported.

NVIDIA NIM exposes OpenAI-compatible APIs for inference in relevant deployments, but the implementation MUST follow the selected endpoint’s current documentation and model requirements [7].

### 30.2 ElevenLabs integration

The ElevenLabs integration MUST support:

- Voice listing.
- Voice profile mapping.
- Text-to-speech generation.
- Streaming where supported.
- Speed control.
- Voice settings.
- Error handling.
- Usage tracking.
- Secure server-side keys.

### 30.3 Render integration

Render deployment SHOULD include:

- Web service.
- Cron Jobs.
- Database.
- Environment configuration.
- Health checks.
- Logs.
- Manual job triggering.
- Deployment status.

Render Cron Jobs use UTC schedules and can be manually triggered for debugging [1].

### 30.4 Calendar integration

Future calendar providers MAY include:

- Google Calendar.
- Microsoft Outlook Calendar.
- CalDAV.
- Internal calendar.

The system MUST distinguish:

- Read calendar.
- Create event.
- Modify event.
- Delete event.
- Invite participants.

### 30.5 Email integration

The system SHOULD distinguish:

- Read email.
- Search email.
- Draft email.
- Send email.
- Delete email.
- Manage labels.

### 30.6 Messaging integration

Each messaging platform MUST have separate permissions.

Examples:

- Read messages.
- Draft response.
- Send response.
- Send media.
- Add reaction.
- Create group.
- Delete message.

### 30.7 Commerce integrations

Shopping integrations SHOULD use approved merchant or browser flows and must never store payment credentials.

***

## 31. Scheduling and Background Jobs

### 31.1 Scheduled jobs

The system MAY run:

- Morning briefing.
- Evening summary.
- Memory consolidation.
- Task stale detection.
- Routine check-ins.
- Deadline monitoring.
- Failed-agent monitoring.
- Price monitoring.
- Website monitoring.
- Certificate monitoring.

### 31.2 Cron design

All jobs MUST:

- Be idempotent.
- Use UTC schedule definitions.
- Convert to user timezone for decisions.
- Use database locks or deduplication.
- Record job runs.
- Record failures.
- Exit cleanly.
- Avoid long-running loops where a scheduled job is sufficient.

### 31.3 Morning briefing logic

The morning briefing SHOULD include:

- Current date.
- Main tasks.
- Important events.
- Overdue tasks.
- Routine reminders due today.
- Pending approvals.
- Agent failures.
- Optional weather and news.

### 31.4 Nightly consolidation

The nightly job SHOULD:

- Summarize conversations.
- Extract memory candidates.
- Merge duplicate tasks.
- Identify stale tasks.
- Update temporal references.
- Calculate next routine occurrences.
- Generate next-day context.
- Delete expired temporary data.

### 31.5 Notification delivery

Notifications MUST record:

- Target channel.
- Scheduled time.
- Actual delivery time.
- Delivery result.
- Deduplication key.
- User preference.
- Quiet-hour decision.

***

## 32. Data Model

### 32.1 Core entities

Required entities:

- User.
- UserPreference.
- Device.
- Session.
- Conversation.
- Message.
- Memory.
- Project.
- Task.
- Event.
- Routine.
- RoutineOccurrence.
- CheckIn.
- Confirmation.
- Agent.
- AgentRun.
- Tool.
- ToolCall.
- Approval.
- Notification.
- AuditLog.
- File.
- VoiceProfile.
- ProviderUsage.

### 32.2 User table

```text
id
email
display_name
preferred_address
timezone
locale
created_at
updated_at
status
```

### 32.3 User preference table

```text
id
user_id
key
value
source
confidence
updated_at
```

### 32.4 Memory table

```text
id
user_id
type
content
structured_value
source_type
source_reference
confidence
importance
sensitivity
privacy_scope
valid_from
valid_until
created_at
updated_at
status
embedding_reference
```

### 32.5 Task table

```text
id
user_id
project_id
title
description
status
priority
created_at
started_at
last_updated_at
due_at
completed_at
blocked_reason
next_action
source_conversation_id
assigned_agent
```

### 32.6 Event table

```text
id
user_id
title
description
event_type
status
local_start
local_end
utc_start
utc_end
timezone
recurrence_rule
source_conversation_id
confirmation_status
created_at
updated_at
```

### 32.7 Routine table

```text
id
user_id
title
description
recurrence_rule
timezone
start_date
end_date
active
check_in_policy
quiet_hours_policy
last_check_in_at
last_confirmed_at
next_due_at
created_from_message
created_at
updated_at
```

### 32.8 Routine occurrence table

```text
id
routine_id
occurrence_date
scheduled_at
status
check_in_sent_at
confirmed_at
confirmation_source
deduplication_key
created_at
updated_at
```

### 32.9 Approval table

```text
id
user_id
tool_name
requested_action
arguments_hash
display_summary
risk_level
data_scope
created_at
expires_at
status
approved_at
approved_by
approval_method
result
```

### 32.10 Agent run table

```text
id
user_id
parent_run_id
agent_name
goal
status
started_at
completed_at
input_scope
output_summary
error
approval_id
```

***

## 33. API Design

### 33.1 API principles

APIs MUST:

- Authenticate users.
- Authorize resource access.
- Validate inputs.
- Enforce schemas.
- Use consistent errors.
- Support idempotency where needed.
- Avoid exposing provider secrets.
- Record sensitive operations.

### 33.2 Suggested endpoints

#### Authentication

```text
POST /auth/register
POST /auth/login
POST /auth/logout
POST /auth/refresh
GET  /auth/sessions
DELETE /auth/sessions/:id
```

#### Conversation

```text
POST /conversations
GET  /conversations
GET  /conversations/:id
POST /conversations/:id/messages
POST /conversations/:id/stop
```

#### Memory

```text
GET    /memories
POST   /memories
PATCH  /memories/:id
DELETE /memories/:id
POST   /memories/search
POST   /memories/forget
```

#### Tasks

```text
GET   /tasks
POST  /tasks
GET   /tasks/:id
PATCH /tasks/:id
POST  /tasks/:id/complete
POST  /tasks/:id/archive
```

#### Routines

```text
GET   /routines
POST  /routines
GET   /routines/:id
PATCH /routines/:id
POST  /routines/:id/disable
GET   /routines/:id/occurrences
POST  /routines/:id/confirm
```

#### Approvals

```text
GET  /approvals
GET  /approvals/:id
POST /approvals/:id/approve
POST /approvals/:id/deny
POST /approvals/:id/revoke
```

#### Voice

```text
GET  /voice/profiles
POST /voice/synthesize
POST /voice/session
```

#### Devices

```text
GET  /devices
POST /devices/register
PATCH /devices/:id
POST /devices/:id/revoke
```

#### Agents

```text
GET  /agents
POST /agent-runs
GET  /agent-runs/:id
POST /agent-runs/:id/stop
```

#### Audit

```text
GET /audit-log
GET /audit-log/:id
```

***

## 34. Error Handling and Reliability

### 34.1 Error categories

- Authentication error.
- Permission error.
- Validation error.
- Provider error.
- Timeout.
- Rate limit.
- Tool failure.
- Agent failure.
- Database failure.
- External service failure.
- Unknown error.

### 34.2 User-facing errors

Errors SHOULD be:

- Clear.
- Brief.
- Actionable.
- Honest.
- Free of secrets.
- Specific about what failed.

Example:

> “I prepared the order, but the merchant checkout timed out. No order confirmation was received, so I did not retry automatically.”

### 34.3 Retry policy

Retries MUST consider:

- Idempotency.
- Action risk.
- Provider error.
- Timeout.
- Duplicate possibility.
- User impact.

Do not automatically retry purchases, messages, payments, or calls unless the provider guarantees idempotent execution.

### 34.4 Partial completion

If a multi-step task partially succeeds, JARVIS MUST report:

- Completed steps.
- Failed steps.
- Remaining steps.
- Data changes.
- Required user action.

### 34.5 Offline or provider unavailable

If NVIDIA or ElevenLabs is unavailable:

- Explain reduced functionality.
- Preserve pending work.
- Avoid losing user messages.
- Do not claim completion.
- Retry later only under policy.
- Provide text fallback if voice fails.

***

## 35. Observability

### 35.1 Metrics

Track:

- Request latency.
- Model latency.
- Voice latency.
- Error rates.
- Tool success rates.
- Approval rates.
- Agent completion rates.
- Notification delivery.
- Duplicate prevention.
- Memory retrieval quality.
- User corrections.
- Provider usage.
- Token usage where available.

### 35.2 Tracing

Each user request SHOULD have a trace ID connecting:

- Conversation.
- Model calls.
- Memory retrieval.
- Agent runs.
- Tool calls.
- Approval.
- External provider calls.
- Final response.

### 35.3 Logging

Logs MUST:

- Avoid secrets.
- Redact sensitive values.
- Use structured format.
- Include correlation IDs.
- Include user scope without exposing unnecessary identity data.
- Record policy decisions.

### 35.4 Health checks

Required health checks:

- Application readiness.
- Database connectivity.
- Provider configuration.
- Queue availability.
- Cron job health.
- Storage availability.

***

## 36. Testing Strategy

### 36.1 Testing layers

The system MUST include:

- Unit tests.
- Integration tests.
- Contract tests.
- Database migration tests.
- Agent workflow tests.
- Prompt and structured-output tests.
- Permission tests.
- Security tests.
- UI tests.
- Browser workflow tests.
- Load tests.
- Failure-recovery tests.
- Multi-day temporal tests.

### 36.2 Temporal test matrix

Test:

- Current day.
- Previous day.
- Next day.
- Monday.
- Tuesday after Monday routine.
- Month boundary.
- Year boundary.
- Daylight-saving timezone changes for future users.
- UTC date different from local date.
- Ambiguous natural dates.

### 36.3 Routine tests

Test:

- Every Monday routine.
- Only today event.
- Planned event.
- Confirmed event.
- Missed occurrence.
- Disabled routine.
- End date.
- Quiet hours.
- Duplicate scheduler run.
- Unanswered check-in.
- Confirmation after check-in.
- Last confirmed occurrence query.

### 36.4 Memory tests

Test:

- Save memory.
- Forget memory.
- Correct memory.
- Expire memory.
- Conflicting memories.
- User isolation.
- Project isolation.
- Sensitive memory access.
- No-memory conversation.
- Memory retrieval relevance.

### 36.5 Permission tests

Test:

- Denied camera.
- Approved single camera frame.
- Expired camera permission.
- Screen permission.
- Send-message approval.
- Changed recipient after approval.
- Changed amount after purchase approval.
- Expired approval.
- Revoked approval.
- Prompt injection attempt.
- Malicious webpage instruction.

### 36.6 Human-like behavior tests

Test:

- “Have you eaten yet, sir?” at 2 PM only when enabled.
- No repeated daily meal question.
- Monday fasting check-in only on Monday.
- No fasting check-in after one-time event.
- Last fasting returns confirmed history.
- Planned activity is not reported as completed.
- Pending work from yesterday is retrieved correctly.

### 36.7 Acceptance criteria

A release is not complete unless:

- All critical tests pass.
- No secrets are exposed.
- Permission checks operate outside the model.
- User data is isolated.
- Scheduled jobs are idempotent.
- Dangerous actions require approval.
- Model failures are handled visibly.
- Memory corrections work.
- Date behavior is correct for Asia/Kolkata.
- UI exposes active sensors and permissions.

***

## 37. Privacy and Human-Like Memory Acceptance Scenarios

### 37.1 Meal check-in

#### Given

- User timezone is Asia/Kolkata.
- Current local time is 2 PM.
- Meal check-ins are enabled.
- No meal has been confirmed today.

#### When

The user starts a conversation.

#### Then

JARVIS MAY say:

> “Have you eaten yet, sir?”

It MUST NOT claim the user has not eaten.

### 37.2 Weekly fasting routine

#### Given

- User says: “Every Monday I fast.”
- Today is Monday.
- The routine is active.
- No check-in has been sent for this occurrence.

#### Then

JARVIS MAY say:

> “How is your fasting going today?”

After one check-in, it MUST NOT ask again for the same occurrence unless the user asks.

### 37.3 One-time fasting

#### Given

- User says: “I am fasting only today.”
- Today is Monday.

#### Then

JARVIS stores a one-time event.

On Tuesday, JARVIS MUST NOT ask about fasting because no recurring routine exists.

### 37.4 Confirmed history

#### Given

- User says: “I fasted today.”

#### Then

JARVIS stores a confirmed historical event.

### 37.5 Last fasting

#### Given

- A confirmed fasting event exists on October 12.
- A planned event exists on October 19.
- A recurring Monday routine exists.

#### When

The user asks:

> “When was my last fasting?”

#### Then

JARVIS says:

> “Your last confirmed fasting day was Monday, October 12. You also have a recurring Monday fasting routine, but the latest occurrence has not been confirmed.”

It MUST NOT answer October 19 because that is only planned.

***

## 38. Free-First Cost Strategy

### 38.1 Development strategy

Use free or low-cost tiers duri