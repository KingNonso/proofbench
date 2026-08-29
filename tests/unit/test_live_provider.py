import importlib

import pytest

from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.live import LiveProvider


def test_live_provider_reports_missing_optional_dependency(monkeypatch) -> None:
    real_import = importlib.import_module

    def import_without_anthropic(name: str):
        if name == "anthropic":
            raise ModuleNotFoundError(name)
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", import_without_anthropic)

    with pytest.raises(EvidenceIncompleteError, match="optional anthropic package"):
        LiveProvider()
