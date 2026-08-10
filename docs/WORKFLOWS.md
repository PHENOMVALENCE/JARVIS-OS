# Workflow guide

Workflows combine explicit actions without giving the language model an unrestricted automation language.

## Workflow object

A workflow contains:

```json
{
  "id": "generated-uuid",
  "name": "Study mode",
  "trigger": {
    "type": "voice",
    "phrase": "start study mode"
  },
  "steps": [
    {
      "type": "action",
      "action": "open_app",
      "arguments": {"name": "notepad"}
    }
  ],
  "enabled": true
}
```

Definitions are JSON-encoded in SQLite. The repository validates a nonempty name, at least one step, supported trigger type, and supported step types.

## Triggers

### Manual

```json
{"type": "manual"}
```

Run from the workflow library.

### Voice or text phrase

```json
{"type": "voice", "phrase": "start study mode"}
```

Matching ignores case and surrounding basic punctuation, but otherwise requires the exact phrase.

### Daily

```json
{"type": "daily", "time": "08:30"}
```

The proactive scheduler checks once per interval and claims a unique `workflow:<id>:<date>` event before running, preventing duplicate daily execution.

## Step types

### Action

```json
{
  "type": "action",
  "action": "set_volume",
  "arguments": {"level": 30},
  "risk": "low",
  "on_error": "stop"
}
```

`type` defaults to `action`. The engine creates a normal `Command` and sends it to `SecureExecutor`; permissions and confirmations are preserved.

`on_error` may be `stop` or any other value to continue. `stop` is the default.

Workflow authors must assign honest risk values. The action's normal router risk is not automatically re-derived from workflow JSON.

### Delay

```json
{"type": "delay", "seconds": 5}
```

Delays are clamped between zero and 300 seconds and wait on the cancellation event.

### Condition

```json
{
  "type": "condition",
  "setting": "privacy_mode",
  "equals": false
}
```

When false, the next step is skipped. Conditions currently compare one runtime setting for exact JSON equality; they do not support arbitrary expressions.

## Editor

Open **WORKFLOWS** to:

- create a definition;
- select and edit an existing workflow;
- choose manual, voice, or daily trigger;
- edit the steps JSON;
- run a workflow in a background thread;
- delete a workflow after confirmation.

The editor reports schema errors before saving.

## Execution history

Each run stores:

- workflow ID;
- start and completion timestamps;
- status (`running`, `completed`, `failed`, or `cancelled`);
- final message.

## Cancellation

Calling `WorkflowEngine.cancel()` sets a shared cancellation event. The engine checks it between steps and during delays. It cannot interrupt a blocking third-party call already inside an action.

## Examples

### Focus mode

```json
[
  {"action": "set_volume", "arguments": {"level": 25}},
  {"action": "open_app", "arguments": {"name": "spotify"}},
  {"type": "delay", "seconds": 2},
  {"action": "open_folder", "arguments": {"path": "Documents"}}
]
```

### Privacy-aware screenshot

```json
[
  {"type": "condition", "setting": "privacy_mode", "equals": false},
  {"action": "screenshot", "arguments": {}, "risk": "medium"}
]
```

## Safe authoring rules

- Prefer named actions over simulated typing.
- Keep destructive steps high risk.
- Use `on_error: stop` for dependent sequences.
- Do not store secrets in workflow arguments.
- Test manually before enabling a daily trigger.
- Keep delays short and cancellable.
