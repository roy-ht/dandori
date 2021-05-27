# flake8: noqa
def handle_pull_request_comment(ctx):
    body = ctx.gh.comment_body().strip()
    if body.startswith("/release"):
        cmd_release(ctx)


def cmd_release(ctx):
    """Merge and release"""
    # check if pull request merged
    pr = ctx.gh.pull_request()
    if not pr.merged:
        ctx.gh.create_comment("Please merge your pull request first!")
        ctx.ops.fail("Please merge your pull request first!")
    target_sha = pr.merge_commit_sha
    tag = _version_from_pyproject_toml(ctx)
    if ctx.gh.has_tag(tag):
        ctx.gh.create_comment(f"Release tag already exists: {tag}")
        ctx.ops.fail(f"Release tag already exists: {tag}")
    ctx.gh.create_release(tag, branch=target_sha, body=f"Release {tag} by #{ctx.gh.issue_number}")


def _version_from_pyproject_toml(ctx):
    conf = ctx.ops.parse_toml(ctx.cfg.cwd.joinpath("pyproject.toml"))
    return conf["tool"]["poetry"]["version"]
