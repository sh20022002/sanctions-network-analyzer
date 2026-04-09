#!/bin/bash
# Security and code quality check script
# Usage: ./security-check.sh [--fix]

set -e

FIX=${1:-}
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo "════════════════════════════════════════════════════════════"
echo "Security & Code Quality Analysis"
echo "════════════════════════════════════════════════════════════"

# Check if dev dependencies are installed
if ! python -c "import bandit" 2>/dev/null; then
    log_error "Dev dependencies not installed"
    echo "Run: pip install -r requirements-dev.txt"
    exit 1
fi

# 1. Check for hardcoded secrets
echo ""
echo "1. Checking for hardcoded secrets..."
if bandit -r analysis/ ingestion/ export/ -f json -o /tmp/bandit-report.json 2>/dev/null; then
    log_info "No obvious hardcoded secrets detected"
else
    log_warn "Issues found in bandit report"
fi

# 2. Dependency vulnerability check
echo ""
echo "2. Checking dependencies for vulnerabilities..."
if safety check -r requirements.txt --json > /tmp/safety-report.json 2>/dev/null; then
    log_info "No known dependency vulnerabilities found"
else
    log_warn "Vulnerabilities may exist - check requirements.txt versions"
fi

# 3. Check .env is not in git
echo ""
echo "3. Verifying .env is gitignored..."
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    log_error ".env is tracked in git! Run: git rm --cached .env"
    exit 1
else
    log_info ".env is properly gitignored"
fi

# 4. Bandit detailed report
echo ""
echo "4. Running Bandit security scan..."
bandit -r analysis/ ingestion/ export/ tests/ --exclude tests/ -ll -f txt

# 5. Type checking with mypy
echo ""
echo "5. Running type checking with mypy..."
if command -v mypy &> /dev/null; then
    mypy analysis/ ingestion/ export/ --ignore-missing-imports || log_warn "Type issues found (non-blocking)"
    log_info "Type check complete"
else
    log_warn "mypy not installed (optional)"
fi

# 6. Pylint check
echo ""
echo "6. Running Pylint..."
if command -v pylint &> /dev/null; then
    pylint analysis/ ingestion/ export/ --max-line-length=100 --disable=C0114,C0115,C0116 --fail-under=8 || log_warn "Pylint issues found"
    log_info "Pylint check complete"
else
    log_warn "pylint not installed (optional)"
fi

# 7. Code formatting check
echo ""
echo "7. Checking code formatting..."
if command -v black &> /dev/null; then
    if [ "$FIX" == "--fix" ]; then
        black analysis/ ingestion/ export/ tests/ --line-length=100
        log_info "Code formatted with Black"
    else
        black --check analysis/ ingestion/ export/ tests/ --line-length=100 || log_warn "Run with --fix to format code"
    fi
fi

if command -v isort &> /dev/null; then
    if [ "$FIX" == "--fix" ]; then
        isort analysis/ ingestion/ export/ tests/ --profile black
        log_info "Imports sorted with isort"
    else
        isort --check-only analysis/ ingestion/ export/ tests/ --profile black || log_warn "Run with --fix to sort imports"
    fi
fi

# Summary
echo ""
echo "════════════════════════════════════════════════════════════"
log_info "Security check complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Review SECURITY.md for recommendations"
echo "  2. Address any HIGH severity issues"
echo "  3. Install pre-commit hooks: pre-commit install"
echo "  4. Use --fix flag to auto-format code"
