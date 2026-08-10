# Plugin and action development

## Directory layout

```text
plugins/
  example/
    manifest.json
    plugin.py
```

Plugins are discovered from immediate subdirectories containing `manifest.json`.

## Manifest

```json
{
  "id": "example",
  "name": "Example Plugin",
  "version": "1.0.0",
  "network": false,
  "actions": {
    "example_read": "low",
    "example_write": "medium"
  }
}
```

Required fields:

- `id`: stable storage and module identifier;
- `name`: user-facing name;
- `version`: plugin version string;
- `actions`: mapping of action name to `low`, `medium`, or `high`.

`network` is displayed in the plugin dashboard. It is a declaration, not an enforced network sandbox.

## Factory

`plugin.py` must define:

```python
def create_plugin(context):
    return Plugin(context)
```

The current context contains:

```python
{"data_dir": Path(...)}
```

Each plugin receives a private directory under the Mark 7 data directory.

## Runtime interface

The instance must provide:

```python
def route(self, text: str):
    # Return (action_name, arguments_dict) or None.

def execute(self, action: str, arguments: dict) -> ActionResult:
    # Return a typed ActionResult.
```

The manager rejects undeclared actions and non-`ActionResult` results. Routing and execution exceptions are captured in plugin status rather than crashing the application worker.

## Lifecycle

1. `PluginManager.discover()` validates manifests.
2. Enabled state is loaded from SQLite; new plugins default enabled.
3. The module is loaded with a unique import name.
4. Declared actions are added to the action map.
5. Plugin routing runs before core deterministic routing.
6. The resulting `Command` passes through `SecureExecutor`.
7. Disabling a plugin re-discovers the directory and removes its routes/actions.

## Example

```python
from jarvis_os.commands import ActionResult


class ExamplePlugin:
    def route(self, text):
        if text.lower().startswith("example remember "):
            return "example_write", {"text": text[17:]}
        return None

    def execute(self, action, arguments):
        if action == "example_write":
            return ActionResult(True, "Example saved.")
        return ActionResult(False, "Unsupported action.")


def create_plugin(context):
    return ExamplePlugin()
```

## Adding a core action

Core actions require changes in three places:

1. Add a deterministic language route in `jarvis_os/router.py`.
2. Register and implement the handler in `jarvis_os/actions.py`.
3. Add router and action tests.

Add the action to the Settings permission list when it cannot be discovered from a plugin manifest.

## Risk selection

- Low: reversible read or ordinary launch/media operation.
- Medium: reads private content, captures a screen, types, clicks, or writes recoverable external data.
- High: sends communications, deletes data, installs software, changes accounts, or may create cost.

Risk is a security property. Do not lower it merely to remove a confirmation dialog.

## Plugin data and credentials

- Store plugin data only under `context["data_dir"]`.
- Retrieve secrets using `CredentialStore`.
- Never store secrets in manifests, logs, workflow definitions, or `ActionResult` messages.
- Set `network: true` whenever the plugin performs network requests.

## Packaging considerations

Plugins are bundled as data in `jarvis.spec` and imported dynamically. Any dependency imported only from plugin files may need an explicit `hiddenimports` entry in the PyInstaller spec.

## Tests

At minimum, test:

- discovery with no error;
- every routing phrase;
- declared risk values;
- successful execution with mocked external services;
- missing credentials;
- network errors and malformed responses;
- disabled state.
