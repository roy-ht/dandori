import dataclasses

import dandori.config
import dandori.gh
import dandori.ops
import dandori.response


@dataclasses.dataclass
class Context:
    gh: dandori.gh.GitHub
    cfg: dandori.config.Config
    ops: dandori.ops.Operation
    resp: dandori.response.Responses
