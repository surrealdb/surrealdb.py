#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}SurrealDB Python SDK Version Testing${NC}"
echo "Python SDK supports v2.0.0 to v2.3.6"

# Define test versions - focus on v2.x as per SDK documentation
V2_VERSIONS=("v2.0.5" "v2.1.8" "v2.2.6" "v2.3.6")
ALL_VERSIONS=("${V2_VERSIONS[@]}")

print_usage() {
    echo "Usage: $0 [options] [version1] [version2] ..."
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  --all               Test all supported v2.x versions"
    echo "  --v2-latest         Test latest minor versions of v2.x"
    echo ""
    echo "Examples:"
    echo "  $0 v2.3.6           Test specific version"
    echo "  $0 --v2-latest      Test latest v2.x versions"  
    echo "  $0 --all            Test all supported versions"
    echo ""
    echo "Supported versions:"
    echo "  v2.x: ${V2_VERSIONS[*]}"
}

cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

run_tests() {
    local version=$1
    local port=${2:-8000}
    
    echo -e "\n${YELLOW}Testing SurrealDB $version${NC}"
    
    # Set environment variables for this test run
    export SURREALDB_VERSION="$version"
    export SURREALDB_URL="http://localhost:$port"
    export TEST_SURREALDB_VERSION="$version"
    export TEST_SURREALDB_PORT="$port"
    
    # Start SurrealDB
    echo "Starting SurrealDB $version on port $port..."
    docker compose up -d surrealdb-test >/dev/null 2>&1
    
    # Wait for startup
    echo "Waiting for SurrealDB to start..."
    sleep 10
    
    # Check if SurrealDB is responding
    for i in {1..30}; do
        if curl -s http://localhost:$port/health >/dev/null 2>&1; then
            echo "SurrealDB is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}SurrealDB failed to start on port $port${NC}"
            return 1
        fi
        sleep 2
    done
    
    # Run tests
    echo "Running tests against SurrealDB $version..."
    if uv run python -m unittest discover -s tests -v; then
        echo -e "${GREEN}✓ Tests passed for SurrealDB $version${NC}"
        return 0
    else
        echo -e "${RED}✗ Tests failed for SurrealDB $version${NC}"
        return 1
    fi
}

# Parse command line arguments
VERSIONS_TO_TEST=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_usage
            exit 0
            ;;
        --all)
            VERSIONS_TO_TEST=("${ALL_VERSIONS[@]}")
            shift
            ;;
        --v2-latest)
            VERSIONS_TO_TEST=("${V2_VERSIONS[@]}")
            shift
            ;;
        v*.*.*)
            VERSIONS_TO_TEST+=("$1")
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# Default to v2 latest if no versions specified
if [ ${#VERSIONS_TO_TEST[@]} -eq 0 ]; then
    VERSIONS_TO_TEST=("v2.3.6")
fi

echo "Testing versions: ${VERSIONS_TO_TEST[*]}"

# Ensure we have uv and dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
uv sync --group dev

# Track results
RESULTS=()
FAILED_VERSIONS=()

# Test each version
for version in "${VERSIONS_TO_TEST[@]}"; do
    # Clean up any existing containers
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    
    if run_tests "$version" 8001; then
        RESULTS+=("✓ $version")
    else
        RESULTS+=("✗ $version")
        FAILED_VERSIONS+=("$version")
    fi
done

# Print summary
echo -e "\n${YELLOW}Test Summary:${NC}"
for result in "${RESULTS[@]}"; do
    if [[ $result == ✓* ]]; then
        echo -e "${GREEN}$result${NC}"
    else
        echo -e "${RED}$result${NC}"
    fi
done

# Exit with error if any tests failed
if [ ${#FAILED_VERSIONS[@]} -gt 0 ]; then
    echo -e "\n${RED}Failed versions: ${FAILED_VERSIONS[*]}${NC}"
    exit 1
else
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
fi 