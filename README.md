# Redis Fuzzer

A robust tool for testing Redis servers by generating and executing random command sequences with advanced fuzzing capabilities.

## Overview

Redis Fuzzer is a Python tool that sends batches of randomly selected Redis commands to a server, optionally applying various fuzzing techniques to test edge cases and server resilience.

## Features

- Executes batches of randomly selected Redis commands
- Seven fuzzing strategies to test server robustness:
  1. Insert random special characters
  2. Duplicate command segments (1-100 characters)
  3. Remove characters
  4. Change character case
  5. Add whitespace characters
  6. Reorder command arguments
  7. Change parameter types (int, float, string, boolean, etc.)
- Pipeline mode for efficient command execution
- Support for both RESP2 and RESP3 protocols
- Comprehensive logging of commands, results, and errors
- Automatic server health verification

## Usage

```
python redisFuzzer.py <IP:PORT> <NUM_BATCHES> --commands-file <FILE> [OPTIONS]
```

### Required Arguments

- `<IP:PORT>` - Redis server address and port (first argument)
- `<NUM_BATCHES>` - Number of command batches to send (second argument)
- `--commands-file, -c <FILE>` - Path to file containing Redis commands

### Optional Arguments

- `--fuzz, -f` - Enable command fuzzing
- `--verbose, -v` - Enable verbose output
- `--pipeline, -p` - Use Redis pipeline for sending commands in batches
- `--resp2` - Use RESP2 protocol (default)
- `--resp3` - Use RESP3 protocol

## Example

```bash
python redisFuzzer.py 127.0.0.1:6379 100 --commands-file commands.txt --fuzz --verbose
```

## Output

The fuzzer generates three log files:
- Command execution log (commands and responses)
- Error log (failures and exceptions)
- Summary log (statistics and execution details)

## Requirements

- Python 3.6+
- redis-py library 
```bash
apt install python3-pip -y
pip install redis
```

## TODO
1. change the code to run by time and not by number of batches
2. add connection timeout in order to kill connections that doesn't finish
3. tcpdump rotating file command
4. python parser for tcpdump output








