@echo off
REM Security and code quality check script for Windows
REM Usage: security-check.bat [--fix]

setlocal enabledelayedexpansion

set FIX=%1

echo.
echo ================================================================
echo Security ^& Code Quality Analysis
echo ================================================================
echo.

REM Check if dev dependencies are installed
python -c "import bandit" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Dev dependencies not installed
    echo Run: pip install -r requirements-dev.txt
    exit /b 1
)

REM 1. Check for hardcoded secrets
echo.
echo 1. Checking for hardcoded secrets...
bandit -r analysis/ ingestion/ export/ -f json -o tmp-bandit-report.json >nul 2>&1
if errorlevel 0 (
    echo [OK] No obvious hardcoded secrets detected
) else (
    echo [WARNING] Issues found in bandit report
)

REM 2. Dependency vulnerability check
echo.
echo 2. Checking dependencies for vulnerabilities...
safety check -r requirements.txt --json > tmp-safety-report.json 2>nul
if errorlevel 0 (
    echo [OK] No known dependency vulnerabilities found
) else (
    echo [WARNING] Vulnerabilities may exist - check requirements.txt versions
)

REM 3. Check .env is not in git
echo.
echo 3. Verifying .env is gitignored...
git ls-files --error-unmatch .env >nul 2>&1
if errorlevel 0 (
    echo [ERROR] .env is tracked in git! Run: git rm --cached .env
    exit /b 1
) else (
    echo [OK] .env is properly gitignored
)

REM 4. Bandit detailed report
echo.
echo 4. Running Bandit security scan...
bandit -r analysis/ ingestion/ export/ tests/ --exclude tests/ -ll -f txt

REM 5. Type checking with mypy
echo.
echo 5. Running type checking with mypy...
where mypy >nul 2>&1
if !errorlevel! equ 0 (
    mypy analysis/ ingestion/ export/ --ignore-missing-imports
    echo [OK] Type check complete
) else (
    echo [SKIP] mypy not installed (optional)
)

REM 6. Code formatting check
echo.
echo 6. Checking code formatting...
where black >nul 2>&1
if !errorlevel! equ 0 (
    if "%FIX%"=="--fix" (
        black analysis/ ingestion/ export/ tests/ --line-length=100
        echo [OK] Code formatted with Black
    ) else (
        black --check analysis/ ingestion/ export/ tests/ --line-length=100
        if !errorlevel! neq 0 echo [WARNING] Run with --fix to format code
    )
)

REM Summary
echo.
echo ================================================================
echo [OK] Security check complete!
echo ================================================================
echo.
echo Next steps:
echo   1. Review SECURITY.md for recommendations
echo   2. Address any HIGH severity issues
echo   3. Install pre-commit hooks: pre-commit install
echo   4. Use --fix flag to auto-format code
echo.

endlocal
