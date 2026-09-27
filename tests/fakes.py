from types import SimpleNamespace


class FakeInterpreter:
    def __init__(self, result=None):
        self.result = result

    async def parse(self, text, lines):
        return self.result


class FakeOpenAI:
    def __init__(self, result=None, error=None):
        self.responses = self
        self.result = result
        self.error = error
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.result)
