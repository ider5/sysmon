"""Optional native extension build; missing rustc must not fail install."""

from __future__ import annotations

import os

from setuptools import setup


def _skip_native_build() -> bool:
    return os.environ.get("SYSMON_SKIP_NATIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


if _skip_native_build():
    setup()
else:
    try:
        from setuptools_rust import Binding, RustExtension
    except ImportError:
        setup()
    else:
        setup(
            rust_extensions=[
                RustExtension(
                    "sysmon._core",
                    path="native/sysmon-core/Cargo.toml",
                    binding=Binding.PyO3,
                    optional=True,
                    debug=False,
                )
            ],
        )
