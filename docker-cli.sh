#!/bin/bash
# sanctions-analyzer Docker utilities

set -e

COMPOSE="docker-compose"
APP="sanctions-analyzer"
NEO4J="sanctions-neo4j"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
Sanctions Analyzer Docker Manager

Usage: ./docker-cli.sh <command> [options]

Commands:
    build               Build Docker images
    up                  Start all services (app + Neo4j)
    down                Stop all services
    clean               Stop services and remove volumes (WARNING: deletes data!)
    restart             Restart all services
    
    run ARGS            Run analysis (e.g., ./docker-cli.sh run --targets data/targets.csv)
    test                Run pytest inside container
    logs [SERVICE]      View logs (app or neo4j)
    shell               Open interactive bash shell in app container
    exec CMD            Execute command in app container
    
    neo4j-browser       Print Neo4j Browser URL
    neo4j-stats         Show Neo4j memory/CPU stats
    neo4j-shell         Open Cypher shell to Neo4j
    
    status              Show container status
    memory              Show memory usage
    ps                  List running containers

Examples:
    ./docker-cli.sh build
    ./docker-cli.sh up
    ./docker-cli.sh run --targets data/targets.csv --neo4j
    ./docker-cli.sh test
    ./docker-cli.sh logs app
    ./docker-cli.sh clean        # WARNING: Removes all data!

EOF
}

# Main commands
case "${1:-}" in
    build)
        log_info "Building Docker images..."
        $COMPOSE build
        log_info "Build complete!"
        ;;
    
    up)
        log_info "Starting services..."
        $COMPOSE up -d
        sleep 5
        log_info "Services started. Waiting for Neo4j to be healthy..."
        sleep 25
        log_info "All services running!"
        $COMPOSE ps
        ;;
    
    down)
        log_info "Stopping services (keeping volumes)..."
        $COMPOSE down
        log_info "Services stopped. Data preserved."
        ;;
    
    clean)
        log_warn "This will stop containers AND DELETE all data (volumes)!"
        read -p "Are you sure? Type 'yes' to continue: " -r
        if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Cleaning up..."
            $COMPOSE down -v
            log_info "All services and data removed."
        else
            log_info "Cleanup cancelled."
        fi
        ;;
    
    restart)
        log_info "Restarting services..."
        $COMPOSE restart
        log_info "Services restarted!"
        $COMPOSE ps
        ;;
    
    run)
        shift
        log_info "Running: python main.py $@"
        $COMPOSE exec -it app python main.py "$@"
        ;;
    
    test)
        log_info "Running tests..."
        $COMPOSE exec app pytest tests/ -v --tb=short
        ;;
    
    logs)
        service="${2:-}"
        if [ -z "$service" ]; then
            log_info "Showing logs from all services (press Ctrl+C to exit)..."
            $COMPOSE logs -f --tail=50
        else
            log_info "Showing logs from $service..."
            $COMPOSE logs -f "$service" --tail=100
        fi
        ;;
    
    shell)
        log_info "Opening bash shell in app container..."
        $COMPOSE exec -it app bash
        ;;
    
    exec)
        shift
        log_info "Executing: $@"
        $COMPOSE exec -it app "$@"
        ;;
    
    neo4j-browser)
        log_info "Neo4j Browser:"
        log_info "URL: http://localhost:7474"
        log_info "User: neo4j"
        log_info "Password: (check .env NEO4J_PASSWORD)"
        ;;
    
    neo4j-stats)
        log_info "Container stats:"
        docker stats $NEO4J --no-stream
        ;;
    
    neo4j-shell)
        log_warn "Neo4j Cypher shell (type ':exit' to quit)..."
        $COMPOSE exec neo4j cypher-shell
        ;;
    
    status)
        log_info "Container status:"
        $COMPOSE ps
        ;;
    
    memory)
        log_info "Memory usage:"
        docker stats --no-stream
        ;;
    
    ps)
        $COMPOSE ps
        ;;
    
    -h|--help|help)
        show_help
        ;;
    
    *)
        log_error "Unknown command: ${1:-empty}"
        echo ""
        show_help
        exit 1
        ;;
esac
