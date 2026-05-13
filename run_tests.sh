#!/bin/bash

# Crazy bash command to extract a list of valid tests
# from the help message of the Python testing suite
# Thank you chat
mapfile -t TESTS < <(
    COLUMNS=1000 python3 test.py -h 2>&1 |
    grep "^  test" |
    sed 's/.*options: //' |
    tr ',' '\n'
)

for test in "${TESTS[@]}"; do
    # Run python and grep, replacing underscores with spaces for the grep check
    python3 test.py "$test" | grep -e "$test" -e "${test//_/ }"
done
