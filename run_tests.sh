#!/bin/bash
# Run tests with various options

echo "====================================="
echo "Facebook Comment Monitor - Test Runner"
echo "====================================="
echo ""

show_menu() {
    echo "Select test option:"
    echo "1. Run all tests"
    echo "2. Run with coverage"
    echo "3. Run unit tests only"
    echo "4. Run integration tests only"
    echo "5. Run specific test file"
    echo "6. Run with pdb (debug on failure)"
    echo "7. Run failed tests only"
    echo "8. Exit"
    echo ""
}

while true; do
    show_menu
    read -p "Enter choice (1-8): " choice
    
    case $choice in
        1)
            echo ""
            echo "Running all tests..."
            pytest tests/ -v
            ;;
        2)
            echo ""
            echo "Running tests with coverage..."
            pytest tests/ --cov=app --cov-report=html --cov-report=term
            echo ""
            echo "Coverage report generated in htmlcov/index.html"
            ;;
        3)
            echo ""
            echo "Running unit tests only..."
            pytest tests/ -v -m unit
            ;;
        4)
            echo ""
            echo "Running integration tests only..."
            pytest tests/ -v -m integration
            ;;
        5)
            echo ""
            read -p "Enter test file (e.g., test_models.py): " testfile
            pytest tests/$testfile -v
            ;;
        6)
            echo ""
            echo "Running tests with pdb (will drop into debugger on failure)..."
            pytest tests/ -v --pdb
            ;;
        7)
            echo ""
            echo "Running failed tests only..."
            pytest tests/ -v --lf
            ;;
        8)
            echo ""
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid choice. Please try again."
            ;;
    esac
    
    echo ""
    echo "====================================="
    echo "Tests completed!"
    echo "====================================="
    echo ""
    read -p "Press Enter to continue..."
done
