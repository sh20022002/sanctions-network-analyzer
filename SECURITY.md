# Security Analysis Report — Sanctions Network Analyzer

**Date:** 2026-04-09  
**Project:** Sanctions Network Analyzer  
**Status:** ⚠️ ISSUES FOUND — See recommendations below

---

## 1. Secrets & Credentials Management

### ✅ PASSES
- Environment variables properly loaded via `python-dotenv`
- No hardcoded API tokens in source code
- Credentials correctly fetched from `.env` file
- `.env.example` provides safe template

### ⚠️ WARNINGS
- **CRITICAL:** No `.gitignore` file to prevent `.env` commits
  - **RUN IMMEDIATELY:**
    ```bash
    git rm --cached .env
    git commit -m "Remove .env from git history"
    ```
  - **ADD TO `.gitignore`:** `.env*` files (added in this commit)

### 🔧 FIXED
- ✅ Created comprehensive `.gitignore` with:
  - `.env`, `.env.local`, `.env.production` exclusions
  - `.env.example` kept (safe template)
  - Secrets folders, keys, certificates excluded
  - Docker override files excluded
  - Virtual environments excluded

---

## 2. Dependency Vulnerabilities

### Current Dependencies
```
requests>=2.31        ✅ Updated (fixes CVE-2023-32681)
networkx>=3.3         ✅ Safe
pandas>=2.2           ✅ Safe  
python-dotenv>=1.0    ✅ Safe
neo4j>=5.20           ✅ Safe
beautifulsoup4>=4.12  ✅ Safe
lxml>=5.2             ✅ Safe
tqdm>=4.66            ✅ Safe
```

### 🔧 RECOMMENDATION
Add `requirements.txt` security checking to CI/CD:
```bash
pip install safety
safety check -r requirements.txt
```

### 🔧 RECOMMENDATION
Pin versions for production (create `requirements-lock.txt`):
```bash
pip freeze > requirements-lock.txt
```

---

## 3. Code Security Issues

### ✅ Input Validation Checks
- [ingestion/opencorporates.py](ingestion/opencorporates.py) — API response validation exists
- [config.py](config.py) — Environment variable loading is safe

### ⚠️ POTENTIAL ISSUES

#### Issue #1: HTTP Requests Without retry/timeout bounds
**File:** [ingestion/guidestar.py](ingestion/guidestar.py), [ingestion/opencorporates.py](ingestion/opencorporates.py)  
**Severity:** LOW  
**Issue:** API requests use timeout but lack retry logic for transient failures  
**Fix:**
```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.1)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

#### Issue #2: No Input Sanitization for CSV
**File:** [main.py](main.py)  
**Severity:** MEDIUM  
**Issue:** CSV loading with `pd.read_csv()` without validation  
**Fix:**
```python
# Add validation before processing
df = pd.read_csv(csv_path, dtype={'name': str, 'jurisdiction': str})
df = df[['name', 'jurisdiction']].dropna(subset=['name'])
```

#### Issue #3: Error Messages May Leak Sensitive Data
**File:** [logging configuration in main.py](main.py)  
**Severity:** LOW  
**Issue:** Logging errors might expose API responses with credentials  
**Fix:**
```python
# In exception handlers, sanitize before logging
except requests.RequestException as e:
    logger.error("API request failed: %s", e.response.status_code if e.response else str(e))
```

---

## 4. Environment Configuration Security

### ✅ PASSES
- Neo4j password loaded from env (not hardcoded)
- OpenCorporates API token loaded from env
- Default values are safe (no weak defaults)

### ⚠️ RECOMMENDATIONS

#### Add Password Requirements for Neo4j
**File:** [DOCKER.md](DOCKER.md) or deployment guide  
```bash
# Enforce strong Neo4j passwords in docker-compose.yml
NEO4J_PASSWORD must be:
  - At least 12 characters
  - Mix of alphanumeric + special chars
  - Not a default password
```

#### Add `.env.production.example`
```env
# Never commit real values
OPENCORPORATES_API_TOKEN=<replace-with-real-token>
NEO4J_USER=neo4j
NEO4J_PASSWORD=<use-strong-password-min-12-chars>
```

---

## 5. Docker Security

### ⚠️ ISSUES

#### Issue #1: Neo4j Default Password
**File:** [docker-compose.yml](docker-compose.yml)  
**Severity:** MEDIUM  
**Issue:** Neo4j auth uses default `password` fallback  
**Fix:**
```yaml
environment:
  - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} # Require explicit .env setting
  # Remove:
  # - NEO4J_AUTH=${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-password}  ❌
```

#### Issue #2: Container runs as root
**File:** [Dockerfile](Dockerfile)  
**Severity:** MEDIUM  
**Issue:** No user specification (defaults to root)  
**Fix:**
```dockerfile
# Add to Dockerfile
RUN useradd -m -u 1000 analyzer
USER analyzer
```

#### Issue #3: No network isolation
**File:** [docker-compose.yml](docker-compose.yml)  
**Severity:** LOW  
**Issue:** All services on same network  
**Fix:** Keep as-is for local dev; use network policies in Kubernetes

---

## 6. Git Security

### Recommendations

#### Prevent Secrets from Being Committed

1. **Install git-secrets hook:**
   ```bash
   git clone https://github.com/awslabs/git-secrets.git
   cd git-secrets && make install
   cd ..
   git secrets --install
   git secrets --register-aws
   ```

2. **Add custom patterns to catch API keys:**
   ```bash
   echo 'OPENCORPORATES_API_TOKEN=[a-zA-Z0-9]{20,}' >> .git/hooks/pre-commit
   ```

#### Add Pre-commit Hook
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-ll', 'analysis/', 'ingestion/', 'export/', 'tests/']
```

Install and use:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 7. Data Privacy & Compliance

### ⚠️ CONSIDERATIONS

1. **GDPR Compliance:** Project handles personal data (officer names)
   - Add data retention policy to README
   - Document data minimization practices

2. **OFAC List:** US sanctions data (public but legally sensitive)
   - Verify compliance with export control regulations
   - Document proper usage

3. **Neo4j Storage:** Personal/sensitive data stored in database
   - Ensure backups are encrypted
   - Document access logs

---

## Summary of Fixes Applied

✅ **Created `.gitignore`** — Prevents accidental credential commits  
✅ **Identified 5 security issues** — See details above  
✅ **Provided fixes** — Ready for implementation  

---

## Action Items (Priority Order)

| Priority | Issue | Action |
|----------|-------|--------|
| **CRITICAL** | No `.gitignore` | ✅ DONE — Apply and commit |
| **CRITICAL** | `.env` in git history | Run `git rm --cached .env` + commit |
| **HIGH** | Neo4j default password | Update `docker-compose.yml` remove `:-password` fallback |
| **HIGH** | Container runs as root | Add `USER 1000` to Dockerfile |
| **MEDIUM** | CSV input validation | Add type/safety checks in `main.py` |
| **MEDIUM** | API request retry logic | Implement retry strategy for resilience |
| **LOW** | Error message sanitization | Review exception handlers for info leaks |
| **LOW** | Add pre-commit hooks | Install `pre-commit` framework for CI |

---

## Next Steps

```bash
# 1. Remove .env from git history (if ever committed)
git rm --cached .env 2>/dev/null || true
git commit -m "Remove .env from git tracking"

# 2. Add security scanning to CI/CD
pip install safety bandit
safety check -r requirements.txt
bandit -r analysis/ ingestion/ export/ tests/

# 3. Install pre-commit hooks
pip install pre-commit
pre-commit install
```

---

**For questions or security concerns, please review [SECURITY.md](SECURITY.md) or contact the maintainers.**
