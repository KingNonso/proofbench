"""The pinned image digest appears in three files. Drift between them would mean
the image a judge pulls is not the image the runner uses.
"""

import re

from proofbench.config import POSTGRES_IMAGE

DIGEST = re.compile(r"postgres:16@sha256:[0-9a-f]{64}")


def test_digest_is_an_index_digest_not_a_tag(repo_root):
    assert DIGEST.fullmatch(POSTGRES_IMAGE)


def test_compose_and_makefile_pin_the_same_image(repo_root):
    for name in ("compose.yaml", "Makefile"):
        found = DIGEST.findall((repo_root / name).read_text())
        assert found, f"{name} does not pin the database image"
        assert set(found) == {POSTGRES_IMAGE}, f"{name} pins a different image"
