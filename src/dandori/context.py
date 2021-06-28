import dataclasses
import typing as T

import dandori.config
import dandori.gh
import dandori.ops
import dandori.response


@dataclasses.dataclass
class Context:
    gh: T.Union[dandori.gh.GitHub, dandori.gh.GitHubMock]
    cfg: dandori.config.Config
    ops: dandori.ops.Operation
    resp: dandori.response.Responses
