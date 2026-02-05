#!/bin/bash
# Run test suite for rezbot refactored components

LOG_FILE="test_results_$(date +%Y%m%d_%H%M%S).log"

echo "========================================"
echo "Running Rezbot Test Suite"
echo "========================================"
echo "Log file: $LOG_FILE"
echo ""

# Activate conda environment (adjust path if needed)
eval "$(/usr/bin/micromamba shell.bash hook)"
micromamba activate rezbot 2>/dev/null || echo "Warning: Could not activate rezbot environment"

# Run all tests and capture output
{
    echo "Test Run Started: $(date)"
    echo "========================================"
    echo ""

    python -m unittest discover -s tests -p "test_*.py" -v

    TEST_EXIT_CODE=$?

    echo ""
    echo "========================================"
    if [ $TEST_EXIT_CODE -eq 0 ]; then
        echo "All tests passed!"
    else
        echo "Some tests failed!"
    fi
    echo "Test Run Finished: $(date)"
    echo "========================================"

    exit $TEST_EXIT_CODE
} 2>&1 | tee "$LOG_FILE"

exit $TEST_EXIT_CODE
