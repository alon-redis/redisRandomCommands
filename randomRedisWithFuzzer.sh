#!/bin/bash
#
# Enhanced Redis Command Fuzzer
# A robust script for testing Redis servers with random command sequences
# with advanced error handling, logging, and fuzzing capabilities
#

set -o pipefail  # Improve error propagation through pipes

# Global variables for tracking resources
TEMP_FILES=()
START_TIME=$(date +%s)

# Signal handler for graceful cleanup
function cleanup {
  local exit_code=$?
  local end_time=$(date +%s)
  local duration=$((end_time - START_TIME))
  
  echo -e "\nCleaning up resources..."
  
  # Remove temporary files
  for file in "${TEMP_FILES[@]}"; do
    if [ -f "$file" ]; then
      rm -f "$file" 2>/dev/null
    fi
  done
  
  # Log summary information if summary log exists
  if [ -n "$SUMMARY_LOG" ] && [ -f "$SUMMARY_LOG" ]; then
    {
      echo "===================================="
      echo "Execution completed at: $(date)"
      echo "Duration: ${duration} seconds"
      echo "Exit code: ${exit_code}"
      if [ $exit_code -eq 0 ]; then
        echo "Status: SUCCESS"
      else
        echo "Status: FAILURE"
      fi
      echo "===================================="
    } >> "$SUMMARY_LOG"
  fi
  
  echo "Execution ${exit_code} completed in ${duration} seconds."
  exit $exit_code
}

# Set trap for various signals
trap cleanup EXIT
trap 'echo "Received interrupt signal."; exit 130' INT TERM

# Display usage information
function show_usage {
  cat << EOF
Usage: $0 <IP:PORT> <numOfBatches> [<commandsFilePath>] [<protocolVersion>] [--fuzz] [--verbose]

Arguments:
  IP:PORT           - Redis server address and port (e.g., 127.0.0.1:6379)
  numOfBatches      - Number of command batches to send
  commandsFilePath  - Path to file containing Redis commands (default: /root/redisCommands30.txt)
  protocolVersion   - Redis protocol version (-2 = RESP2, -3 = RESP3, default: -2)
  --fuzz            - Enable command fuzzing
  --verbose         - Enable verbose output

Examples:
  $0 127.0.0.1:6379 10
  $0 redis.example.com:6380 100 /path/to/commands.txt -3 --fuzz
EOF
  exit 1
}

# Parse and validate command line arguments
function parse_arguments {
  # Check minimum arguments
  if [ "$#" -lt 2 ]; then
    show_usage
  fi
  
  # Parse IP:PORT
  if ! [[ "$1" =~ ^([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|[a-zA-Z0-9.-]+):[0-9]+$ ]]; then
    echo "Error: Invalid IP:PORT format: '$1'. Expected format: IP:PORT"
    exit 1
  fi
  
  IFS=':' read -r IP PORT <<< "$1"
  
  # Validate port number
  if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "Error: Port must be a number between 1-65535"
    exit 1
  fi
  
  # Validate number of batches
  NUM_BATCHES=$2
  if ! [[ "$NUM_BATCHES" =~ ^[0-9]+$ ]] || [ "$NUM_BATCHES" -lt 1 ]; then
    echo "Error: Number of batches must be a positive integer"
    exit 1
  fi
  
  # Parse optional arguments
  COMMANDS_FILE=${3:-"/root/redisCommands30.txt"}
  PROTOCOL_VERSION=${4:--2}  # Default to RESP2 if not provided
  
  # Check for flag arguments
  FUZZ_ENABLED=false
  VERBOSE=false
  for arg in "$@"; do
    case "$arg" in
      --fuzz)
        FUZZ_ENABLED=true
        ;;
      --verbose)
        VERBOSE=true
        ;;
    esac
  done
  
  # Validate commands file
  if [ ! -f "$COMMANDS_FILE" ]; then
    echo "Error: Commands file '$COMMANDS_FILE' does not exist"
    exit 1
  fi
  
  if [ ! -r "$COMMANDS_FILE" ]; then
    echo "Error: Cannot read commands file '$COMMANDS_FILE' (permission denied)"
    exit 1
  fi
  
  if [ ! -s "$COMMANDS_FILE" ]; then
    echo "Error: Commands file '$COMMANDS_FILE' is empty"
    exit 1
  fi
  
  # Get the length of the commands file
  file_length=$(wc -l < "$COMMANDS_FILE")
  if [ "$file_length" -lt 1 ]; then
    echo "Error: No valid commands found in '$COMMANDS_FILE'"
    exit 1
  fi
  
  # Validate protocol version
  if [[ ! "$PROTOCOL_VERSION" =~ ^-[23]$ ]]; then
    echo "Warning: Unsupported protocol version '$PROTOCOL_VERSION', using default -2"
    PROTOCOL_VERSION="-2"
  fi
}

# Set up logging directories and files
function setup_logging {
  # Create log directories with error handling
  LOG_DIR="/var/log/redis-fuzzer"
  if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_DIR="/tmp/redis-fuzzer"
    mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="/tmp"
  fi

  # Create unique log files
  TIMESTAMP=$(date +%Y%m%d%H%M%S)
  UUID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$$-$RANDOM")
  OUTPUT_FILE="${LOG_DIR}/redis-commands-${TIMESTAMP}-${UUID}.log"
  ERROR_LOG="${LOG_DIR}/redis-errors-${TIMESTAMP}-${UUID}.log"
  SUMMARY_LOG="${LOG_DIR}/redis-summary-${TIMESTAMP}-${UUID}.log"
  
  # Check if logs are writable
  if ! touch "$OUTPUT_FILE" 2>/dev/null || ! touch "$ERROR_LOG" 2>/dev/null || ! touch "$SUMMARY_LOG" 2>/dev/null; then
    echo "Warning: Cannot write to log directory, using fallback location"
    OUTPUT_FILE="/tmp/redis-commands-${TIMESTAMP}-${UUID}.log"
    ERROR_LOG="/tmp/redis-errors-${TIMESTAMP}-${UUID}.log"
    SUMMARY_LOG="/tmp/redis-summary-${TIMESTAMP}-${UUID}.log"
    touch "$OUTPUT_FILE" "$ERROR_LOG" "$SUMMARY_LOG"
  fi
  
  # Record basic execution details
  {
    echo "===================================="
    echo "Redis Fuzzer Execution Summary"
    echo "===================================="
    echo "Started: $(date)"
    echo "Target: $IP:$PORT"
    echo "Batches: $NUM_BATCHES"
    echo "Fuzzing: $FUZZ_ENABLED"
    echo "Verbose: $VERBOSE"
    echo "Commands file: $COMMANDS_FILE (${file_length} commands)"
    echo "Protocol version: $PROTOCOL_VERSION"
    echo "===================================="
    echo
    echo "Execution Log:"
  } > "$SUMMARY_LOG"
  
  # Add files to cleanup list
  TEMP_FILES+=("$OUTPUT_FILE" "$ERROR_LOG" "$SUMMARY_LOG")
  
  # Print log locations
  echo "Logs will be saved to:"
  echo "  - Commands: $OUTPUT_FILE"
  echo "  - Errors: $ERROR_LOG"
  echo "  - Summary: $SUMMARY_LOG"
}

# Test Redis connectivity
function test_redis_connectivity {
  local timeout_seconds=3
  echo -n "Testing connectivity to Redis at $IP:$PORT... "
  
  if ! command -v redis-cli &>/dev/null; then
    echo "Failed"
    echo "Error: redis-cli not found in PATH. Please install redis-tools."
    exit 1
  fi
  
  # Attempt connection with timeout
  if ! timeout $timeout_seconds redis-cli -h "$IP" -p "$PORT" PING > /dev/null 2>&1; then
    echo "Failed"
    echo "Error: Cannot connect to Redis server at $IP:$PORT"
    {
      echo "[$(date +%H:%M:%S)] Failed to connect to Redis server at $IP:$PORT"
      echo "Verify that:"
      echo "  - The Redis server is running"
      echo "  - The IP address and port are correct"
      echo "  - Network connectivity and firewalls allow the connection"
    } >> "$SUMMARY_LOG"
    exit 1
  fi
  
  echo "Success"
  echo "[$(date +%H:%M:%S)] Successfully connected to Redis server at $IP:$PORT" >> "$SUMMARY_LOG"
}

# Function to select a random Redis command from file
function random_command {
  # Defense against file_length changes during execution
  local max_attempts=5
  local attempts=0
  local cmd=""
  
  while [ -z "$cmd" ] && [ $attempts -lt $max_attempts ]; do
    local current_length=$(wc -l < "$COMMANDS_FILE" 2>/dev/null || echo "$file_length")
    local line_num=$(( (RANDOM % current_length) + 1 ))
    cmd=$(sed "${line_num}q;d" "$COMMANDS_FILE" 2>/dev/null)
    attempts=$((attempts + 1))
  done
  
  if [ -z "$cmd" ]; then
    # Fallback to a safe command if we can't get one from the file
    echo "PING"
  else
    echo "$cmd"
  fi
}

# Advanced fuzzing function with multiple strategies
function fuzz_command {
  local command="$1"
  
  # Skip fuzzing if disabled or empty command
  if [ "$FUZZ_ENABLED" = false ] || [ -z "$command" ]; then
    echo "$command"
    return
  fi
  
  # Select a fuzzing strategy
  local fuzz_strategy=$((RANDOM % 5))
  
  case $fuzz_strategy in
    0) # Insert random special character
      local special_chars='!@#$%^&*()_-+=<>?/;:[]{}|\\\"~'
      local rand_index=$((RANDOM % (${#command} + 1))) # +1 to allow insertion at end
      local rand_special_index=$((RANDOM % ${#special_chars}))
      local special_char=${special_chars:$rand_special_index:1}
      echo "${command:0:rand_index}$special_char${command:rand_index}"
      ;;
      
    1) # Duplicate a portion of the command
      if [ ${#command} -le 2 ]; then
        echo "$command"
        return
      fi
      local start_pos=$((RANDOM % (${#command} - 1)))
      local length=$((1 + RANDOM % 3)) # 1-3 chars
      if [ $((start_pos + length)) -gt ${#command} ]; then
        length=$((${#command} - start_pos))
      fi
      local portion=${command:$start_pos:$length}
      echo "${command:0:start_pos}$portion$portion${command:$((start_pos+length))}"
      ;;
      
    2) # Remove characters
      if [ ${#command} -le 3 ]; then
        echo "$command"
        return
      fi
      local start_pos=$((1 + RANDOM % (${#command} - 2))) # Don't remove first char
      local length=$((1 + RANDOM % 2)) # Remove 1-2 chars
      echo "${command:0:start_pos}${command:$((start_pos+length))}"
      ;;
      
    3) # Change case of a character
      local words=($command)
      if [ ${#words[@]} -gt 0 ] && [ ${#words[0]} -gt 1 ]; then
        # Change case of a random character in the first word (usually the command name)
        local word=${words[0]}
        local char_pos=$((RANDOM % ${#word}))
        local char=${word:$char_pos:1}
        
        # Toggle case with tr command
        if [[ "$char" =~ [A-Z] ]]; then
          local new_char=$(echo "$char" | tr 'A-Z' 'a-z')
        else
          local new_char=$(echo "$char" | tr 'a-z' 'A-Z')
        fi
        
        # Reconstruct the command
        words[0]="${word:0:char_pos}$new_char${word:$((char_pos+1))}"
        echo "${words[*]}"
      else
        echo "$command"
      fi
      ;;
      
    4) # Add whitespace characters
      local whitespace_chars=(' ' $'\t' $'\n' $'\r')
      local rand_index=$((RANDOM % (${#command} + 1)))
      local rand_ws=${whitespace_chars[$((RANDOM % ${#whitespace_chars[@]}))]}
      echo "${command:0:rand_index}$rand_ws${command:rand_index}"
      ;;
  esac
}

# Execute a batch of commands
function execute_batch {
  local batch_num=$1
  local pipeline_size=$(( (RANDOM % 10) + 1 ))
  
  # Create temporary files for this batch
  local commands_file=$(mktemp "/tmp/redis-batch-cmds-XXXXXX")
  local result_file=$(mktemp "/tmp/redis-batch-result-XXXXXX")
  local error_file=$(mktemp "/tmp/redis-batch-error-XXXXXX")
  TEMP_FILES+=("$commands_file" "$result_file" "$error_file")
  
  # Generate commands
  local commands=()
  for (( i=0; i<pipeline_size; i++ )); do
    local cmd=$(random_command)
    local fuzzed_cmd=$(fuzz_command "$cmd")
    commands+=("$fuzzed_cmd")
    echo "$fuzzed_cmd" >> "$commands_file"
  done
  
  # Add a PING to verify server is responsive
  echo "PING" >> "$commands_file"
  
  # Log batch information
  {
    echo -e "\n==== BATCH $batch_num ===="
    echo "Time: $(date +%H:%M:%S)"
    echo "Pipeline size: $pipeline_size"
    echo "Commands:"
    cat "$commands_file"
  } >> "$OUTPUT_FILE"
  
  # Execute commands with timeout and error handling
  local start_time=$(date +%s.%N)
  local timeout_seconds=5
  local exit_code=0
  
  if ! timeout $timeout_seconds redis-cli -h "$IP" -p "$PORT" $PROTOCOL_VERSION < "$commands_file" > "$result_file" 2> "$error_file"; then
    exit_code=$?
    local error_output=$(cat "$error_file")
    local result_output=$(cat "$result_file")
    
    {
      echo "EXECUTION FAILED (code $exit_code)"
      if [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ]; then
        echo "TIMEOUT: Redis server did not respond within $timeout_seconds seconds"
      fi
      if [ -n "$error_output" ]; then
        echo "ERRORS:"
        echo "$error_output"
      fi
      if [ -n "$result_output" ]; then
        echo "PARTIAL RESULTS:"
        echo "$result_output"
      fi
    } >> "$OUTPUT_FILE"
    
    echo "Batch $batch_num FAILED (exit code: $exit_code)" >> "$SUMMARY_LOG"
    
    if [ "$VERBOSE" = true ]; then
      echo "Batch $batch_num FAILED (exit code: $exit_code)"
      if [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ]; then
        echo "- Timeout occurred, server may be unresponsive"
      elif [ -n "$error_output" ]; then
        echo "- Error: ${error_output:0:100}..."
      fi
    fi
  else
    local result_output=$(cat "$result_file")
    local execution_time=$(echo "$(date +%s.%N) - $start_time" | bc)
    
    {
      echo "EXECUTION SUCCEEDED (${execution_time}s)"
      if [ -n "$result_output" ]; then
        echo "RESULTS:"
        echo "$result_output"
      fi
    } >> "$OUTPUT_FILE"
    
    if [ "$VERBOSE" = true ]; then
      echo "Batch $batch_num succeeded (${execution_time%.*}ms)"
    else
      # Print a progress indicator
      if [ $((batch_num % 10)) -eq 0 ] || [ "$batch_num" -eq "$NUM_BATCHES" ]; then
        echo -n "."
        if [ $((batch_num % 50)) -eq 0 ] || [ "$batch_num" -eq "$NUM_BATCHES" ]; then
          echo " $batch_num/$NUM_BATCHES"
        fi
      fi
    fi
  fi
  
  # Wait a small random time between requests to avoid overwhelming the server
  sleep 0.$(( RANDOM % 5 + 1 ))
  
  return $exit_code
}

# Main execution function
function main {
  local failed_batches=0
  local success_batches=0
  
  echo "Starting Redis command fuzzer with $NUM_BATCHES batches..."
  if [ "$FUZZ_ENABLED" = true ]; then
    echo "Fuzzing enabled: Commands will be randomly modified to test edge cases"
  fi
  
  echo "[$(date +%H:%M:%S)] Beginning execution of $NUM_BATCHES batches" >> "$SUMMARY_LOG"
  
  # Process each batch
  for (( batch_num=1; batch_num<=NUM_BATCHES; batch_num++ )); do
    if ! execute_batch "$batch_num"; then
      failed_batches=$((failed_batches + 1))
      
      # If we have 3 consecutive failures, check connectivity
      if [ $failed_batches -ge 3 ] && [ $((batch_num - failed_batches)) -eq 0 ]; then
        echo "Multiple consecutive failures. Checking Redis server..."
        if ! timeout 2 redis-cli -h "$IP" -p "$PORT" PING > /dev/null 2>&1; then
          echo "Error: Lost connection to Redis server at $IP:$PORT"
          echo "[$(date +%H:%M:%S)] Lost connection to Redis server after $batch_num batches" >> "$SUMMARY_LOG"
          break
        fi
      fi
    else
      success_batches=$((success_batches + 1))
      # Reset consecutive failure counter on success
      failed_batches=0
    fi
  done
  
  # Print summary
  echo
  echo "Execution completed:"
  echo "- Total batches: $batch_num"
  echo "- Successful batches: $success_batches"
  echo "- Failed batches: $failed_batches"
  
  # Record summary
  {
    echo
    echo "===================================="
    echo "Execution Statistics:"
    echo "- Total batches executed: $batch_num"
    echo "- Successful batches: $success_batches"
    echo "- Failed batches: $failed_batches"
    if [ $failed_batches -gt 0 ]; then
      echo "- Failure rate: $(echo "scale=2; $failed_batches * 100 / $batch_num" | bc)%"
    else
      echo "- Failure rate: 0%"
    fi
  } >> "$SUMMARY_LOG"
  
  echo "Logs saved to:"
  echo "  - Commands: $OUTPUT_FILE"
  echo "  - Summary: $SUMMARY_LOG"
}

# Execute the script
parse_arguments "$@"
setup_logging
test_redis_connectivity
main
exit 0
