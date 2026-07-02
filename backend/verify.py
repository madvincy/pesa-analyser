import sys
packages = [
    "fastapi", "uvicorn", "pydantic", "sqlalchemy",
    "pdfplumber", "pandas", "numpy", "openai",
    "anthropic", "transformers", "reportlab", "matplotlib",
]

exit_code = 0
for pkg in packages:
    try:
        __import__(pkg)
    except ImportError:
        exit_code = 1

sys.exit(exit_code)
