# dandori: GitHub Actions with Python

dandori runs on your Actions, and automate workflow with using Python.

**Current Status is Super Early Alpha. DO NOT USE IT in your production repository.**


## How to Use

First, You need to define workflow.
You can hook any [events](https://docs.github.com/en/actions/reference/events-that-trigger-workflows) without manual/scheduled workflow such as `pull_request`, `push` or `pull_request_review`.

```yaml
name: dandori_action
on: [pull_request, issue_comment]

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install dandori
      - run: dandori run
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Next, you can write your Python script or package on your repo, like `dandori_handler.py` or 'dandori_handlers/'. dandori automatically import your code and run handler functions defined in your code:

```py
## dandori_handler.py

def handle_pull_request(ctx):
    if ctx.gh.payload.action == 'synchronize':
        ctx.gh.create_comment("You pushed new commits!!")


def handle_pull_request_comment(ctx):
    """It's a special handler type, issue_comment event on PR"""
    comment_body = ctx.gh.comment_body().strip()
    if comment_body.startswith('/some-command'):
        some_code_as_you_like()
```

If you want more than one file, you need to make a package:

```py
## handlers/__init__.py
# Must be relative imports
from .pull_request import handle_pull_request
from .issue import handle_issue

## handlers/pull_request.py
def handle_pull_request(ctx):
    ...

## -- handlers/issue.py
def handle_issue(ctx):
    ...
```

## Configuration

dandori supports `pyproject.toml`, or make any toml file as you like (default is `dandori.toml`).

In pyproject.toml, write config in `tool.dandori` section:

```toml
# pyproject.toml
[tool.dandori]
handlers = ['path/to/handler']
```

In independent toml file, write config in `dandori` section:

```toml
# dandori.toml
[dandori]
handlers = ['path/to/handler']
```


## Use case

### Share CI code with multiple repo:


```yaml
name: dandori_action
on: [pull_request, issue_comment]

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/checkout@v2
        with:
          repository: your/dandori-handler
          ref: v1  # something you need
          ssh-key: ${{ secrets.your_repo_key }}
          path: dandori-handler
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install dandori
      - run: dandori run -f dandori-handler/dandori.toml
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Use third party package in handler

Your handler module or package will be imported dynamically, so you can install any library in the "(virtual)env" same as dandori installed.

Most simple cale, install dandori with other library:

```
# Install libraries with pip
- run: pip install dandori requests python-dateutil
```

If you want use just a "command" and not to use global env, use `ctx.ops.run_venv()`:

```py
def handle_pull_request(ctx):
    ctx.ops.run_venv(["pip", "install", "twine"])
    ctx.ops.run_venv(['twine', 'upload', 'dist/*'])
```

Or dynamically install it and use it:

```py
import importlib

def handle_pull_request(ctx):
    ctx.ops.run(["pip", "install", "requests"])
    requests = importlib.import_module('requests')
```