#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lagrange Tactical AI - Python Package Setup Script
===================================================

Infinite Lagrange AI Tactical Analysis Center.
Full-stack game AI agent for fleet combat simulation, ship database intelligence,
and RAG-powered tactical decision support using DeepSeek LLM.

Setup script supporting both pure Python and compiled extensions.
"""
import os
import sys
import platform
from pathlib import Path
from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
from setuptools.command.develop import develop

HERE = Path(__file__).resolve().parent
SRC_DIR = HERE / "src"
VERSION_FILE = HERE / "VERSION"


def get_version():
    """Read version from VERSION file or fall back to hardcoded."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "2.0.0"


def get_readme():
    """Read README.rst or README.md."""
    for filename in ("README.rst", "README.md"):
        readme_path = HERE / filename
        if readme_path.exists():
            return readme_path.read_text(encoding="utf-8")
    return "Lagrange Tactical AI - Infinite Lagrange Fleet Combat Analysis Platform"


def get_requirements(filename="requirements.txt"):
    """Parse requirements file."""
    req_path = HERE / filename
    if not req_path.exists():
        return []
    lines = req_path.read_text(encoding="utf-8").splitlines()
    requirements = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            if ";" in line:
                line = line.split(";")[0].strip()
            requirements.append(line)
    return requirements


def get_extensions():
    """Build C/C++ extensions for the Lagrange battle engine core.

    The battle engine uses compiled extensions for performance-critical
    path computation. Falls back gracefully to pure Python if compilation
    is not available.
    """
    extensions = []
    system = platform.system().lower()
    is_windows = system == "windows"

    cpp_sources = [
        str(SRC_DIR / "lagrange" / "engine" / "battle_core.cpp"),
        str(SRC_DIR / "lagrange" / "engine" / "damage_calc.cpp"),
        str(SRC_DIR / "lagrange" / "engine" / "intercept_model.cpp"),
        str(SRC_DIR / "lagrange" / "engine" / "fleet_pathfinder.cpp"),
    ]
    cpp_headers = [
        str(SRC_DIR / "lagrange" / "engine" / "battle_core.h"),
        str(SRC_DIR / "lagrange" / "engine" / "damage_calc.h"),
        str(SRC_DIR / "lagrange" / "engine" / "intercept_model.h"),
        str(SRC_DIR / "lagrange" / "engine" / "fleet_pathfinder.h"),
    ]

    existing_sources = [s for s in cpp_sources if os.path.exists(s)]
    existing_headers = [h for h in cpp_headers if os.path.exists(h)]

    if existing_sources:
        compile_args = []
        link_args = []
        define_macros = [
            ("LAGRANGE_VERSION", f'"{get_version()}"'),
            ("PY_SSIZE_T_CLEAN", None),
        ]

        if is_windows:
            compile_args.extend(["/O2", "/arch:AVX2", "/std:c++17", "/EHsc"])
            define_macros.append(("_CRT_SECURE_NO_WARNINGS", None))
        else:
            compile_args.extend(["-O3", "-march=native", "-std=c++17", "-fPIC"])
            link_args.append("-flto")

        battle_ext = Extension(
            name="lagrange.engine._battle_engine",
            sources=existing_sources,
            depends=existing_headers,
            include_dirs=[
                str(SRC_DIR / "lagrange" / "engine"),
                str(SRC_DIR),
            ],
            libraries=[],
            extra_compile_args=compile_args,
            extra_link_args=link_args,
            define_macros=define_macros,
            language="c++",
        )
        extensions.append(battle_ext)

    cython_src = SRC_DIR / "lagrange" / "engine" / "fleet_solver.pyx"
    if cython_src.exists():
        try:
            from Cython.Build import cythonize
            extensions.extend(
                cythonize(
                    [str(cython_src)],
                    compiler_directives={
                        "language_level": "3",
                        "boundscheck": False,
                        "wraparound": False,
                        "cdivision": True,
                    },
                )
            )
        except ImportError:
            print("Cython not available, skipping fleet_solver compilation", file=sys.stderr)

    return extensions


class LagrangeBuildExt(build_ext):
    """Custom build_ext that handles missing compilers gracefully."""

    def run(self):
        try:
            super().run()
        except Exception as exc:
            print(
                f"WARNING: Could not build C extensions: {exc}\n"
                "The Lagrange AI will run in pure Python mode (slower but functional).",
                file=sys.stderr,
            )


class LagrangeInstall(install):
    """Custom install that verifies dependencies and creates data dirs."""

    user_options = install.user_options + [
        ("with-gpu", None, "Install with GPU acceleration support"),
        ("with-all", None, "Install with all optional dependencies"),
    ]

    boolean_options = install.boolean_options + ["with-gpu", "with-all"]

    def initialize_options(self):
        super().initialize_options()
        self.with_gpu = False
        self.with_all = False

    def run(self):
        super().run()
        data_dirs = [
            HERE / "data",
            HERE / "data" / "ships",
            HERE / "data" / "battles",
            HERE / "chroma_db",
            HERE / "db_backup",
            HERE / "logs",
        ]
        for d in data_dirs:
            d.mkdir(parents=True, exist_ok=True)
        print("Lagrange AI installation complete. Run 'lagrange-server' to start.")


class LagrangeDevelop(develop):
    """Custom develop install for editable mode."""

    def run(self):
        super().run()
        print("Lagrange AI installed in development mode. Happy hacking!")


setup(
    name="lagrange-tactical-ai",
    version=get_version(),
    description="Infinite Lagrange AI Tactical Analysis Center",
    long_description=get_readme(),
    long_description_content_type="text/x-rst",
    author="Lagrange AI Community",
    author_email="dev@lagrange-ai.dev",
    maintainer="Core Engineering Team",
    maintainer_email="core@lagrange-ai.dev",
    url="https://github.com/lagrange-ai/tactical-center",
    project_urls={
        "Documentation": "https://docs.lagrange-ai.dev",
        "Source": "https://github.com/lagrange-ai/tactical-center",
        "Tracker": "https://github.com/lagrange-ai/tactical-center/issues",
        "Discord": "https://discord.gg/lagrange-ai",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Framework :: FastAPI",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Chinese (Simplified)",
        "Natural Language :: English",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: C++",
        "Programming Language :: JavaScript",
        "Topic :: Games/Entertainment :: Simulation",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    keywords=[
        "infinite-lagrange",
        "game-ai",
        "tactical-analysis",
        "fleet-simulation",
        "ship-combat",
        "rag",
        "deepseek",
        "vector-search",
        "strategy-game",
        "space-combat",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "lagrange": [
            "data/*.json",
            "data/*.csv",
            "data/ships/*.json",
            "templates/*.html",
            "templates/*.jinja2",
            "static/**/*",
            "locales/**/*.po",
            "locales/**/*.mo",
            "py.typed",
        ],
    },
    exclude_package_data={
        "": ["*.pyc", "__pycache__", "*.so", "*.pyd"],
    },
    zip_safe=False,
    python_requires=">=3.10,<3.13",
    install_requires=get_requirements(),
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "black>=24.0.0",
            "isort>=5.13.0",
            "ruff>=0.1.0",
            "mypy>=1.8.0",
            "pre-commit>=3.6.0",
            "coverage>=7.4.0",
            "ipython>=8.18.0",
        ],
        "gpu": [
            "faiss-gpu>=1.7.4",
            "torch>=2.1.0",
            "onnxruntime-gpu>=1.16.0",
        ],
        "docs": [
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=2.0.0",
            "myst-parser>=2.0.0",
        ],
        "monitoring": [
            "prometheus-fastapi-instrumentator>=6.0.0",
            "opentelemetry-api>=1.21.0",
            "opentelemetry-sdk>=1.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "lagrange-server=lagrange.main:run_server",
            "lagrange-cli=lagrange.cli:main",
            "lagrange-import=lagrange.data_import:main",
            "lagrange-export=lagrange.export:main",
            "lagrange-backup=lagrange.admin:backup_command",
        ],
    },
    ext_modules=get_extensions(),
    cmdclass={
        "build_ext": LagrangeBuildExt,
        "install": LagrangeInstall,
        "develop": LagrangeDevelop,
    },
    include_package_data=True,
)
