# flake8: noqa


def handle_pull_request_comment(ctx):
    body = ctx.gh.comment_body().strip()
    if body.startswith("/standby-release"):
        cmd_standby_release(ctx)
        cmd_check_release(ctx)
    elif body.startswith("/release"):
        cmd_release()
    else:
        if ctx.gh.has_label("release"):
            cmd_check_release(ctx)


def handle_pull_request(ctx):
    pr = ctx.gh.pull_request()
    if ctx.gh.has_label("release") and ctx.gh.payload["action"] == "closed" and pr.merged:
        cmd_release(ctx)


def cmd_standby_release(ctx):
    # Add label to PR
    ctx.gh.add_or_create_label("release", color="000000")


def cmd_check_release(ctx):
    """Release test"""
    pr = ctx.gh.pull_request()
    tag = _get_release_tag(ctx)
    # upload to test pypi
    files = _release_to_pypi(ctx, tag)
    ctx.gh.create_comment("Uploaded files to test PyPI: " + ", ".join(x.name for x in files))


def cmd_release(ctx):
    # check if pull request merged
    pr = ctx.gh.pull_request()
    if not pr.merged:
        ctx.gh.create_comment("Please merge your pull request first!")
        ctx.ops.fail("Please merge your pull request first!")
    target_sha = pr.merge_commit_sha
    tag = _get_release_tag(ctx)
    # upload to pypi
    files = _release_to_pypi(ctx, tag, test=False)
    ctx.gh.create_release(tag, branch=target_sha, body=f"Release {tag} by #{ctx.gh.issue_number}")
    ctx.gh.create_comment("Uploaded files to PyPI: " + ", ".join(x.name for x in files))


def cmd_hello(ctx):
    ctx.gh.create_comment(f"Hello^^ {ctx.cfg.options.hello.name}")


def _release_to_pypi(ctx, tag, test=True):
    ctx.ops.run_venv(["pip", "install", "twine", "poetry"])
    if test:
        tag = f"{tag}.dev{ctx.gh.run_id}"
        _set_version(ctx, tag)
    ctx.ops.run_venv(["poetry", "build"])
    files = list(ctx.cfg.cwd.joinpath("dist").iterdir())
    twine_args = ["twine", "upload", "--non-interactive", "--config-file", str(ctx.cfg.cwd.joinpath(".pypirc"))]
    if test:
        twine_args += ["-r", "testpypi"]
    twine_args += [str(x) for x in files]
    ctx.ops.run_venv(twine_args)
    return files


def _get_release_tag(ctx):
    tag = _get_version(ctx)
    if ctx.gh.has_tag(tag):
        ctx.gh.create_comment(f"Release tag already exists: {tag}")
        ctx.ops.fail(f"Release tag already exists: {tag}")
    return tag


def _get_version(ctx):
    conf = ctx.ops.parse_toml(ctx.cfg.cwd.joinpath("pyproject.toml"))
    return conf["tool"]["poetry"]["version"]


def _set_version(ctx, tag):
    path = ctx.cfg.cwd.joinpath("pyproject.toml")
    conf = ctx.ops.parse_toml(path)
    conf["tool"]["poetry"]["version"] = tag
    ctx.ops.dump_toml(conf, path)
