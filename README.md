# Redis Fuzzer Tool

A robust Redis command fuzzing tool for testing Redis servers with random command sequences.

## Overview

The Redis Fuzzer is an advanced testing tool designed to test Redis servers for robustness and stability by sending randomized and optionally fuzzed Redis commands. It helps identify potential issues with Redis server implementations by triggering edge cases and unexpected inputs.

## Features

- Sends random Redis commands from a provided command file
- Optional command fuzzing with multiple fuzzing strategies:
  - Special character insertion
  - Command portion duplication
  - Character removal
  - Case manipulation
  - Whitespace insertion
  - Argument reordering
  - Parameter type changes
- Support for RESP2 and RESP3 protocols
- Pipeline mode for batch command execution
- Comprehensive logging of commands, errors, and execution results
- Server connectivity monitoring with automatic termination after repeated failures
- Robust error handling and resource cleanup

## Fuzzing Strategies

The tool implements seven distinct mutation-based fuzzing strategies to trigger edge cases in Redis server implementations:

1. **Special Character Insertion**: Inserts random special characters (`!@#$%^&*()_-+=<>?/;:[]{}|\\"~`) at random positions within commands to test input validation, parser resilience, and injection vulnerabilities.

2. **Command Portion Duplication**: Selects a random segment (1-100 characters) within the command and duplicates it in-place. This tests how the Redis command parser handles redundant or unexpected patterns, potentially triggering buffer overflow conditions or parser state confusion.

3. **Character Removal**: Systematically removes 1-2 characters from random positions, typically preserving the command's first character. This strategy tests the server's ability to handle truncated or incomplete commands while maintaining partial semantic validity.

4. **Case Manipulation**: Randomly modifies the case of characters within command names, challenging case-sensitive parsing and command resolution mechanisms. Redis commands are typically case-insensitive, but edge cases in implementations may cause parsing failures.

5. **Whitespace Insertion**: Injects various whitespace characters (space, tab, newline, carriage return) at random positions. Tests parser resilience against irregular tokenization and command boundary detection.

6. **Argument Reordering**: Implements three distinct reordering techniques:
   - Complete shuffling of all arguments while preserving the command name
   - Selective swap of two randomly chosen arguments
   - Relocation of the command name to an arbitrary position within the arguments

7. **Parameter Type Transformation**: Mutates argument types using six distinct approaches:
   - Conversion to 32-bit signed integers (range: -2147483648 to 2147483647)
   - Conversion to large positive integers near INT32_MAX
   - Conversion to floating-point values with 5-digit precision
   - Conversion to quoted strings with random numeric suffixes
   - Conversion to boolean representations (true/false/1/0)
   - Conversion to negative integers (range: -1 to -1000000)

These strategies comprehensively test the Redis protocol parser, command handler, and memory management system against malformed inputs, ensuring robust error handling and prevention of potential security vulnerabilities.

## Requirements

- Python 3.6+
- `redis` Python package

## Installation

```bash
apt install python3-pip -y
pip3 install redis
```

## Usage

```bash
python3 redisFuzzer.py <IP:PORT> <NUM_BATCHES> --commands-file <FILE> [OPTIONS]
```

### Required Arguments

- `<IP:PORT>`: Redis server address and port (e.g., 127.0.0.1:6379)
- `<NUM_BATCHES>`: Number of command batches to execute
- `--commands-file`, `-c`: Path to file containing Redis commands

### Optional Arguments

- `--fuzz`, `-f`: Enable command fuzzing
- `--verbose`, `-v`: Enable verbose output
- `--pipeline`, `-p`: Use Redis pipeline for sending commands in batches
- `--resp2`: Use RESP2 protocol (default)
- `--resp3`: Use RESP3 protocol

## Example Command File

The command file should contain valid Redis commands, one per line. For example:

```
SET key1 value1
GET key1
HSET hash1 field1 value1
HGET hash1 field1
LPUSH list1 item1 item2 item3
LRANGE list1 0 -1
```

## Example Usage

Basic usage:
```bash
python3 redisFuzzer.py 127.0.0.1:6379 100 --commands-file redis_commands.txt
```

With fuzzing and verbose output:
```bash
python3 redisFuzzer.py 127.0.0.1:6379 100 --commands-file redis_commands.txt --fuzz --verbose
```

Using RESP3 protocol and pipeline mode:
```bash
python3 redisFuzzer.py 127.0.0.1:6379 100 --commands-file redis_commands.txt --resp3 --pipeline
```

## Log Files

The tool generates three log files:

1. **Commands Log**: Records all commands sent and their responses
2. **Error Log**: Records any errors encountered during execution
3. **Summary Log**: Provides an execution summary with statistics

Log files are saved by default to `/var/log/redis-fuzzer/` or `/tmp/redis-fuzzer/` depending on write permissions.

## Exit Codes

- `0`: Successful execution
- `1`: Error during execution (connectivity issues, command errors, etc.)
- `130`: Termination due to interrupt signal (Ctrl+C)

## Signal Handling

The tool properly handles SIGINT and SIGTERM signals, ensuring clean resource cleanup upon interruption.

## Notes

- The tool includes server liveness checking via ECHO commands
- Automatically terminates after 5 consecutive ECHO failures
- Random delays between batches to prevent overwhelming the server
- Command fuzzing is random and may generate invalid commands, which helps test Redis server's error handling 










