def handle_issue_comment(ctx):
    """handle issue_comment event, some slash command"""
    body = ctx.gh.comment_body()
    if body.startswith("/greet"):
        print("Local greet command invoked!!!")
