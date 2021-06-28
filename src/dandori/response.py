from __future__ import annotations


class Response(dict):
    """Manage running i/o"""


class Responses:
    def __init__(self):
        """Response of user defined function"""
        self._responses = []

    def append(self, name: str, resp: Response):
        """append last called response"""
        self._responses.append({"name": name, "response": resp})

    def append_dict(self, name: str, resp: dict):
        """append last called response (dict format)"""
        self.append(name, Response(resp))

    def get(self, name=None):
        """Get last called function response"""
        if not self._responses:
            return None
        if name is None:
            return self._responses[-1]["response"]
        for resp in self._responses:
            if resp["name"] == name:
                return resp["response"]
        raise ValueError(f"Response {name} not found")
