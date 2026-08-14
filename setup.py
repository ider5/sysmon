"""Optional native extension build; missing rustc must not fail install."""

from setuptools import setup

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
