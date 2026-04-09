@echo off
REM sanctions-analyzer Docker utilities for Windows

setlocal enabledelayedexpansion

set COMPOSE=docker-compose
set APP=sanctions-analyzer
set NEO4J=sanctions-neo4j

REM Colors would require additional tools, skipping for simplicity

if "%1"=="" (
    goto show_help
)

if /i "%1"=="build" (
    echo [INFO] Building Docker images...
    !COMPOSE! build
    echo [INFO] Build complete!
    goto end
)

if /i "%1"=="up" (
    echo [INFO] Starting services...
    !COMPOSE! up -d
    timeout /t 5
    echo [INFO] Services started. Waiting for Neo4j to be healthy...
    timeout /t 25
    echo [INFO] All services running!
    !COMPOSE! ps
    goto end
)

if /i "%1"=="down" (
    echo [INFO] Stopping services (keeping volumes)...
    !COMPOSE! down
    echo [INFO] Services stopped. Data preserved.
    goto end
)

if /i "%1"=="clean" (
    echo [WARN] This will stop containers AND DELETE all data!
    set /p confirm="Are you sure? Type 'yes' to continue: "
    if /i "!confirm!"=="yes" (
        echo [INFO] Cleaning up...
        !COMPOSE! down -v
        echo [INFO] All services and data removed.
    ) else (
        echo [INFO] Cleanup cancelled.
    )
    goto end
)

if /i "%1"=="restart" (
    echo [INFO] Restarting services...
    !COMPOSE! restart
    echo [INFO] Services restarted!
    !COMPOSE! ps
    goto end
)

if /i "%1"=="run" (
    echo [INFO] Running: python main.py %*
    shift
    !COMPOSE! exec -it app python main.py %*
    goto end
)

if /i "%1"=="test" (
    echo [INFO] Running tests...
    !COMPOSE! exec app pytest tests/ -v --tb=short
    goto end
)

if /i "%1"=="logs" (
    if "%2"=="" (
        echo [INFO] Showing logs from all services...
        !COMPOSE! logs -f --tail=50
    ) else (
        echo [INFO] Showing logs from %2...
        !COMPOSE! logs -f %2 --tail=100
    )
    goto end
)

if /i "%1"=="shell" (
    echo [INFO] Opening bash shell in app container...
    !COMPOSE! exec -it app bash
    goto end
)

if /i "%1"=="exec" (
    shift
    echo [INFO] Executing: %*
    !COMPOSE! exec -it app %*
    goto end
)

if /i "%1"=="neo4j-browser" (
    echo [INFO] Neo4j Browser:
    echo URL: http://localhost:7474
    echo User: neo4j
    echo Password: (check .env NEO4J_PASSWORD)
    goto end
)

if /i "%1"=="neo4j-shell" (
    echo [INFO] Neo4j Cypher shell (type ':exit' to quit)...
    !COMPOSE! exec neo4j cypher-shell
    goto end
)

if /i "%1"=="status" (
    echo [INFO] Container status:
    !COMPOSE! ps
    goto end
)

if /i "%1"=="memory" (
    echo [INFO] Memory usage:
    docker stats --no-stream
    goto end
)

if /i "%1"=="ps" (
    !COMPOSE! ps
    goto end
)

if /i "%1"=="-h" goto show_help
if /i "%1"=="--help" goto show_help
if /i "%1"=="help" goto show_help

echo [ERROR] Unknown command: %1
echo.
goto show_help

:show_help
echo Sanctions Analyzer Docker Manager
echo.
echo Usage: docker-cli.bat ^<command^> [options]
echo.
echo Commands:
echo   build               Build Docker images
echo   up                  Start all services (app is+ Neo4j)
echo   down                Stop all services
echo   clean               Stop services and remove volumes (WARNING: deletes data!)
echo   restart             Restart all services
echo.
echo   run ARGS            Run analysis (e.g., docker-cli.bat run --targets ^data\targets.csv)
echo   test                Run pytest inside container
echo   logs [SERVICE]      View logs (app or neo4j)
echo   shell               Open interactive bash shell in app container
echo   exec CMD            Execute command in app container
echo.
echo   neo4j-browser       Print Neo4j Browser URL
echo   neo4j-shell         Open Cypher shell to Neo4j
echo.
echo   status              Show container status
echo   memory              Show memory usage
echo   ps                  List running containers
echo.
echo Examples:
echo   docker-cli.bat build
echo   docker-cli.bat up
echo   docker-cli.bat run --targets data\targets.csv --neo4j
echo   docker-cli.bat test
echo   docker-cli.bat logs app
echo   docker-cli.bat clean      (WARNING: Removes all data!)
echo.

:end
endlocal
