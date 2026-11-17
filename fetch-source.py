#!/usr/bin/env python3
"""Download the official, pinned sources, including web2py submodules."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import urllib.request

SOURCES = [
    (
        'eden',
        'sahana',
        '5cc0fe1d2cf7cc4d58c6939a6e8d085b7d3c00a9',
        '945c4284fb0c88181ba6779049cd4f3100f688f4dad8072a425b73375b360e7d',
    ),
    (
        'web2py',
        'web2py',
        '9005306c50ab2125c265bad8f4a9dacc56d460a1',
        '9dbfa293bc4f1db77b2f11ba29a7b3cdde567cc3c91316a3900df884ff9854ad',
    ),
    (
        'pydal',
        'web2py',
        'b515c362e83006e79f681ff6491e4a4ab8566acb',
        'e6a62c3cc7b3af4adfe34fd2f0519032bdbb751554619191504d17244e520603',
    ),
    (
        'rocket3',
        'web2py',
        '4154030489ebab15b96d1f90a6f288cf4f64dd23',
        '2d718891f4b5d12e3cb192b21dd6b82baed39f512d582c47d8fceaef5bb840fe',
    ),
    (
        'yatl',
        'web2py',
        'c6983a51909f76c48f4a40c93eea7f485321cd3f',
        '5bacd150a8c53581e7bb68bca500e7cd853f52080aacddceaa2f1b5853daef1d',
    ),
]

destination = Path(__file__).resolve().parent / "source"
if destination.exists():
    raise SystemExit("source already exists; use the existing pinned source")
with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
    root = Path(temporary) / "source"
    for name, owner, revision, digest in SOURCES:
        url = f"https://codeload.github.com/{owner}/{name}/tar.gz/{revision}"
        print(f"Downloading {owner}/{name}@{revision}", flush=True)
        data = urllib.request.urlopen(url, timeout=180).read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"Checksum mismatch: {name}")
        target = root / "web2py"
        if name == "eden":
            target = target / "applications" / "eden"
        elif name != "web2py":
            target = target / "gluon" / "packages" / name
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts[1:]
                if not parts:
                    continue
                member.name = str(Path(*parts))
                archive.extract(member, target, filter="data")
    root.rename(destination)
