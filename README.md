# redisRandomCommands

Of course! Here's a **short and clear README** you can use for your **Enhanced Redis Command Fuzzer** script:

---

# Enhanced Redis Command Fuzzer

A **robust and flexible Bash script** to test Redis servers by sending **randomized sequences** of Redis commands, optionally applying **fuzzing techniques** to uncover edge cases, and **logging** detailed execution results.

## Features
- Random selection and execution of Redis commands
- Optional **command fuzzing** (mutate, alter, or inject special characters)
- Supports both **RESP2** and **RESP3** protocols
- Graceful **cleanup and error handling**
- Detailed **logging** (commands, errors, and summary)
- **Connectivity check** to the Redis server
- Auto-handling of **temporary files** and **signal interrupts**

## Usage

```bash
./redis_fuzzer.sh <IP:PORT> <numOfBatches> [<commandsFilePath>] [<protocolVersion>] [--fuzz] [--verbose]
```

### Arguments
- `IP:PORT` – Redis server address (e.g., `127.0.0.1:6379`)
- `numOfBatches` – Number of command batches to send
- `commandsFilePath` – (Optional) File containing Redis commands (default: `/root/redisCommands30.txt`)
- `protocolVersion` – (Optional) Protocol version (`-2` for RESP2, `-3` for RESP3; default: `-2`)
- `--fuzz` – (Optional) Enable random command fuzzing
- `--verbose` – (Optional) Show detailed per-batch execution output

### Examples
```bash
./redis_fuzzer.sh 127.0.0.1:6379 10
./redis_fuzzer.sh redis.example.com:6380 100 /path/to/commands.txt -3 --fuzz --verbose
```

## Output
- **Command log:** List of sent commands
- **Error log:** Captured errors and timeouts
- **Summary log:** Execution statistics and status overview

Logs are saved in `/var/log/redis-fuzzer/` or `/tmp/redis-fuzzer/` depending on permissions.

## Requirements
- `redis-cli` must be installed and available in the system `PATH`
- Bash 4.x or higher recommended
