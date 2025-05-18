#!/usr/bin/env python3
"""
Enhanced Redis Command Fuzzer
A robust script for testing Redis servers with random command sequences
with advanced error handling, logging, and fuzzing capabilities.
Python implementation of the original bash script.
"""

import argparse
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import socket
import redis
from datetime import datetime
from pathlib import Path


class RedisFuzzer:
    def __init__(self):
        self.temp_files = []
        self.start_time = time.time()
        self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        """Set up handlers for clean termination"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        """Handle termination signals"""
        print("\nReceived interrupt signal.")
        self.cleanup(130)
        
    def cleanup(self, exit_code=0):
        """Clean up resources before exiting"""
        end_time = time.time()
        duration = int(end_time - self.start_time)
        
        print("\nCleaning up resources...")
        
        # Remove temporary files but not log files
        for file in self.temp_files:
            if os.path.isfile(file):
                try:
                    os.remove(file)
                except OSError:
                    pass
        
        # Log summary information
        if hasattr(self, 'summary_log') and os.path.isfile(self.summary_log):
            with open(self.summary_log, 'a') as f:
                f.write("====================================\n")
                f.write(f"Execution completed at: {datetime.now()}\n")
                f.write(f"Duration: {duration} seconds\n")
                f.write(f"Exit code: {exit_code}\n")
                f.write(f"Status: {'SUCCESS' if exit_code == 0 else 'FAILURE'}\n")
                f.write("====================================\n")
        
        # Display location of log files that are preserved
        if hasattr(self, 'log_files') and hasattr(self, 'output_file') and hasattr(self, 'summary_log'):
            print("Log files preserved at:")
            print(f"  - Commands: {self.output_file}")
            print(f"  - Errors: {self.error_log}")
            print(f"  - Summary: {self.summary_log}")
        
        print(f"Execution completed with code {exit_code} in {duration} seconds.")
        sys.exit(exit_code)
        
    def parse_arguments(self):
        """Parse and validate command line arguments"""
        parser = argparse.ArgumentParser(
            description='Redis Command Fuzzer',
            usage='%(prog)s <IP:PORT> <NUM_BATCHES> --commands-file <FILE> [OPTIONS]',
            epilog='Example: python3 redisFuzzer.py 127.0.0.1:6379 100 --commands-file randomRedisCommands.txt --fuzz --verbose'
        )
        
        # Required positional arguments
        parser.add_argument('target', 
                          help='Redis server address and port (e.g., 127.0.0.1:6379)')
        parser.add_argument('num_batches', type=int,
                          help='Number of command batches to send')
        
        # Required named argument
        parser.add_argument('--commands-file', '-c', required=True,
                          help='Path to file containing Redis commands')
        
        # Optional arguments
        parser.add_argument('--fuzz', '-f', action='store_true', 
                          help='Enable command fuzzing')
        parser.add_argument('--verbose', '-v', action='store_true', 
                          help='Enable verbose output')
        parser.add_argument('--pipeline', '-p', action='store_true',
                          help='Use Redis pipeline for sending commands in batches')
        
        # Protocol version group (mutually exclusive)
        protocol_group = parser.add_mutually_exclusive_group()
        protocol_group.add_argument('--resp2', action='store_true', default=True,
                                  help='Use RESP2 protocol (default)')
        protocol_group.add_argument('--resp3', action='store_false', dest='resp2',
                                  help='Use RESP3 protocol')
        
        # Let argparse handle errors and help display
        args = parser.parse_args()
        
        # Validate target format
        if ':' not in args.target:
            print("\nError: Invalid target format. Expected format: IP:PORT")
            print("The first argument must be the Redis server address and port.")
            sys.exit(1)
            
        self.ip, port_str = args.target.split(':')
        
        # Validate port number
        try:
            self.port = int(port_str)
            if not 1 <= self.port <= 65535:
                print("\nError: Port must be a number between 1-65535")
                sys.exit(1)
        except ValueError:
            print("\nError: Port must be a number")
            sys.exit(1)
            
        # Validate number of batches
        try:
            if args.num_batches < 1:
                print("\nError: Number of batches must be a positive integer")
                print("The second argument must be the number of batches to send.")
                sys.exit(1)
        except (ValueError, TypeError):
            print("\nError: Second argument must be a valid number of batches (integer)")
            sys.exit(1)
            
        self.num_batches = args.num_batches
        
        # Validate commands file
        self.commands_file = args.commands_file
        if not os.path.isfile(self.commands_file):
            print(f"\nError: Commands file '{self.commands_file}' does not exist")
            sys.exit(1)
            
        if not os.access(self.commands_file, os.R_OK):
            print(f"\nError: Cannot read commands file '{self.commands_file}' (permission denied)")
            sys.exit(1)
            
        # Check if file is empty
        if os.path.getsize(self.commands_file) == 0:
            print(f"\nError: Commands file '{self.commands_file}' is empty")
            sys.exit(1)
            
        # Count number of lines in the file
        with open(self.commands_file, 'r') as f:
            self.file_length = sum(1 for _ in f)
            
        if self.file_length < 1:
            print(f"\nError: No valid commands found in '{self.commands_file}'")
            sys.exit(1)
            
        # Store remaining arguments
        self.fuzz_enabled = args.fuzz
        self.verbose = args.verbose
        self.protocol_resp2 = args.resp2
        self.use_pipeline = args.pipeline
        
        return args
        
    def setup_logging(self):
        """Set up logging directories and files"""
        # Try to create log directory
        log_dir = "/var/log/redis-fuzzer"
        if not os.access("/var/log", os.W_OK):
            log_dir = "/tmp/redis-fuzzer"
            
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            log_dir = "/tmp"
            
        # Create unique log files
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        uid = str(uuid.uuid4())
        self.output_file = f"{log_dir}/redis-commands-{timestamp}-{uid}.log"
        self.error_log = f"{log_dir}/redis-errors-{timestamp}-{uid}.log"
        self.summary_log = f"{log_dir}/redis-summary-{timestamp}-{uid}.log"
        
        # Initialize log_files list if it doesn't exist
        if not hasattr(self, 'log_files'):
            self.log_files = []
        
        # Check if logs are writable
        try:
            for logfile in [self.output_file, self.error_log, self.summary_log]:
                with open(logfile, 'w') as f:
                    pass
                self.log_files.append(logfile)  # Track log files separately
        except OSError:
            # Fallback to tmp directory
            self.output_file = f"/tmp/redis-commands-{timestamp}-{uid}.log"
            self.error_log = f"/tmp/redis-errors-{timestamp}-{uid}.log"
            self.summary_log = f"/tmp/redis-summary-{timestamp}-{uid}.log"
            
            for logfile in [self.output_file, self.error_log, self.summary_log]:
                with open(logfile, 'w') as f:
                    pass
                self.log_files.append(logfile)  # Track log files separately
        
        # Write initial summary log
        with open(self.summary_log, 'w') as f:
            f.write("====================================\n")
            f.write("Redis Fuzzer Execution Summary\n")
            f.write("====================================\n")
            f.write(f"Started: {datetime.now()}\n")
            f.write(f"Target: {self.ip}:{self.port}\n")
            f.write(f"Batches: {self.num_batches}\n")
            f.write(f"Fuzzing: {self.fuzz_enabled}\n")
            f.write(f"Verbose: {self.verbose}\n")
            f.write(f"Protocol: RESP{3 if not self.protocol_resp2 else 2}\n")
            f.write(f"Pipeline mode: {'Enabled' if self.use_pipeline else 'Disabled'}\n")
            f.write(f"Commands file: {self.commands_file} ({self.file_length} commands)\n")
            f.write("====================================\n\n")
            f.write("Execution Log:\n")
            
        # Print log locations
        print("Logs will be saved to:")
        print(f"  - Commands: {self.output_file}")
        print(f"  - Errors: {self.error_log}")
        print(f"  - Summary: {self.summary_log}")
            
    def test_redis_connectivity(self):
        """Test connectivity to Redis server using Redis Python client"""
        timeout_seconds = 3
        print(f"Testing connectivity to Redis at {self.ip}:{self.port}... ", end='')
        
        try:
            # Try to connect using Redis Python client
            redis_client = redis.Redis(
                host=self.ip, 
                port=self.port, 
                socket_timeout=timeout_seconds,
                socket_connect_timeout=timeout_seconds,
                protocol=2 if self.protocol_resp2 else 3  # Set protocol version based on args
            )
            
            # Execute a simple PING command
            if not redis_client.ping():
                raise redis.ConnectionError("Ping returned False")
                
            redis_client.close()
                
        except (redis.ConnectionError, redis.TimeoutError, socket.error) as e:
            print("Failed")
            print(f"Error: Cannot connect to Redis server at {self.ip}:{self.port}")
            print(f"Details: {str(e)}")
            
            with open(self.summary_log, 'a') as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to connect to Redis server at {self.ip}:{self.port}\n")
                f.write(f"Error details: {str(e)}\n")
                f.write("Verify that:\n")
                f.write("  - The Redis server is running\n")
                f.write("  - The IP address and port are correct\n")
                f.write("  - Network connectivity and firewalls allow the connection\n")
                
            sys.exit(1)
            
        print("Success")
        with open(self.summary_log, 'a') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully connected to Redis server at {self.ip}:{self.port}\n")
            
    def random_command(self):
        """Select a random Redis command from file"""
        max_attempts = 5
        attempts = 0
        cmd = ""
        
        while not cmd and attempts < max_attempts:
            try:
                # Get current file length in case it changed
                current_length = sum(1 for _ in open(self.commands_file, 'r'))
                line_num = random.randint(1, current_length)
                
                with open(self.commands_file, 'r') as f:
                    for i, line in enumerate(f, 1):
                        if i == line_num:
                            cmd = line.strip()
                            break
            except:
                pass
                
            attempts += 1
            
        # Fallback to a safe command if we can't get one from the file
        if not cmd:
            return "PING"
            
        return cmd
        
    def fuzz_command(self, command):
        """Advanced fuzzing function with multiple strategies"""
        # Skip fuzzing if disabled or empty command
        if not self.fuzz_enabled or not command:
            return command
            
        # Select a fuzzing strategy
        fuzz_strategy = random.randint(0, 6)  # Updated to include new strategy
        
        if fuzz_strategy == 0:
            # Insert random special character
            special_chars = '!@#$%^&*()_-+=<>?/;:[]{}|\\\"~'
            rand_index = random.randint(0, len(command))
            special_char = random.choice(special_chars)
            return command[:rand_index] + special_char + command[rand_index:]
            
        elif fuzz_strategy == 1:
            # Duplicate a larger portion of the command
            if len(command) <= 2:
                return command
                
            # Choose a starting position for duplication
            start_pos = random.randint(0, len(command) - 1)
            
            # Choose a length between 1 and 100 characters
            length = random.randint(1, min(100, len(command) - start_pos))
            
            # Extract the portion to duplicate
            portion = command[start_pos:start_pos+length]
            
            # Insert the duplicated portion back into the command
            return command[:start_pos] + portion + portion + command[start_pos+length:]
            
        elif fuzz_strategy == 2:
            # Remove characters
            if len(command) <= 3:
                return command
                
            start_pos = random.randint(1, len(command) - 2)  # Don't remove first char
            length = random.randint(1, 2)  # Remove 1-2 chars
            
            return command[:start_pos] + command[start_pos+length:]
            
        elif fuzz_strategy == 3:
            # Change case of a character
            words = command.split()
            
            if words and len(words[0]) > 1:
                # Change case of a random character in the first word (usually the command name)
                word = words[0]
                char_pos = random.randint(0, len(word) - 1)
                char = word[char_pos]
                
                # Toggle case
                if char.isupper():
                    new_char = char.lower()
                else:
                    new_char = char.upper()
                    
                # Reconstruct the command
                words[0] = word[:char_pos] + new_char + word[char_pos+1:]
                return ' '.join(words)
            else:
                return command
                
        elif fuzz_strategy == 4:
            # Add whitespace characters
            whitespace_chars = [' ', '\t', '\n', '\r']
            rand_index = random.randint(0, len(command))
            rand_ws = random.choice(whitespace_chars)
            
            return command[:rand_index] + rand_ws + command[rand_index:]
        
        elif fuzz_strategy == 5:
            # Reorder command arguments
            words = command.split()
            
            # Need at least command name + 2 arguments to reorder
            if len(words) < 3:
                return command
                
            # Preserve the command name (first word) and shuffle the rest
            cmd_name = words[0]
            arguments = words[1:]
            
            # Select reordering strategy
            reorder_type = random.randint(0, 2)
            
            if reorder_type == 0:
                # Complete shuffle of all arguments
                random.shuffle(arguments)
                return cmd_name + ' ' + ' '.join(arguments)
                
            elif reorder_type == 1:
                # Swap two random arguments
                if len(arguments) >= 2:
                    idx1 = random.randint(0, len(arguments) - 1)
                    idx2 = random.randint(0, len(arguments) - 1)
                    # Make sure we're selecting different indices
                    while idx1 == idx2 and len(arguments) > 1:
                        idx2 = random.randint(0, len(arguments) - 1)
                        
                    arguments[idx1], arguments[idx2] = arguments[idx2], arguments[idx1]
                    return cmd_name + ' ' + ' '.join(arguments)
                    
            elif reorder_type == 2:
                # Move command name to random position
                all_parts = [cmd_name] + arguments
                cmd_pos = random.randint(0, len(all_parts) - 1)
                
                # Remove command name from first position and insert at new position
                all_parts.pop(0)
                all_parts.insert(cmd_pos, cmd_name)
                
                return ' '.join(all_parts)
        
        elif fuzz_strategy == 6:
            # Change parameter types
            words = command.split()
            
            # Need at least command name + 1 argument to change parameter type
            if len(words) < 2:
                return command
                
            # Preserve the command name
            cmd_name = words[0]
            arguments = words[1:]
            
            # Select a random argument to change
            if not arguments:
                return command
                
            arg_idx = random.randint(0, len(arguments) - 1)
            orig_arg = arguments[arg_idx]
            
            # Define parameter type transformations
            param_type = random.randint(0, 5)
            
            if param_type == 0:
                # Convert to integer
                new_arg = str(random.randint(-2147483648, 2147483647))
            elif param_type == 1:
                # Convert to large int32
                new_arg = str(random.randint(1000000000, 2147483647))
            elif param_type == 2:
                # Convert to float
                new_arg = f"{random.uniform(-1000000, 1000000):.5f}"
            elif param_type == 3:
                # Convert to string with quotes
                new_arg = f'"{orig_arg}_{random.randint(1, 1000)}"'
            elif param_type == 4:
                # Convert to boolean
                new_arg = random.choice(["true", "false", "1", "0"])
            elif param_type == 5:
                # Convert to negative number
                new_arg = f"-{random.randint(1, 1000000)}"
            
            # Replace the argument with the new type
            arguments[arg_idx] = new_arg
            
            # Reconstruct the command
            return cmd_name + ' ' + ' '.join(arguments)
            
        return command
        
    def execute_batch(self, batch_num):
        """Execute a batch of commands using Redis Python client"""
        pipeline_size = random.randint(1, 10)
        
        # Log batch information
        with open(self.output_file, 'a') as f:
            f.write(f"\n==== BATCH {batch_num} ====\n")
            f.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"Pipeline size: {pipeline_size}\n")
            f.write(f"Protocol: RESP{3 if not self.protocol_resp2 else 2}\n")
            f.write(f"Pipeline mode: {'Enabled' if self.use_pipeline else 'Disabled'}\n")
            f.write("Commands:\n")
        
        # Create ECHO command to verify server is alive
        echo_value = f"ALIVE_CHECK_{batch_num}"
        echo_command = f"ECHO {echo_value}"
        
        # Add ECHO command to log file
        with open(self.output_file, 'a') as f:
            # If using pipeline, indicate ECHO will run on separate connection
            if self.use_pipeline:
                f.write(f"{echo_command} (on separate connection)\n")
            else:
                f.write(f"{echo_command}\n")
        
        # Generate commands list
        commands = []
        
        # Add the random commands to our command list
        for _ in range(pipeline_size):
            cmd = self.random_command()
            fuzzed_cmd = self.fuzz_command(cmd)
            commands.append(fuzzed_cmd)
            
            with open(self.output_file, 'a') as f:
                f.write(f"{fuzzed_cmd}\n")
                
        # Log the commands list creation
        with open(self.output_file, 'a') as f:
            f.write(f"Generated {len(commands)} commands for {'pipeline' if self.use_pipeline else 'sequential'} execution\n")
                
        # Execute commands with timeout and error handling
        start_time = time.time()
        timeout_seconds = 5
        exit_code = 0
        result_output = ""
        error_output = ""
        echo_check_passed = False
        
        try:
            # Create a Redis client for main commands
            redis_client = redis.Redis(
                host=self.ip, 
                port=self.port, 
                socket_timeout=timeout_seconds,
                socket_connect_timeout=timeout_seconds,
                decode_responses=not self.use_pipeline,  # Only auto-decode in non-pipeline mode
                protocol=2 if self.protocol_resp2 else 3  # Set protocol version based on args
            )
            
            # First, perform ECHO check on a separate connection if using pipeline
            if self.use_pipeline:
                with open(self.output_file, 'a') as f:
                    f.write("Performing ECHO check on separate connection...\n")
                    
                # Create a separate connection for the ECHO check
                echo_client = redis.Redis(
                    host=self.ip, 
                    port=self.port, 
                    socket_timeout=timeout_seconds,
                    socket_connect_timeout=timeout_seconds,
                    decode_responses=True,
                    protocol=2 if self.protocol_resp2 else 3
                )
                
                try:
                    # Execute ECHO command on separate connection
                    echo_response = echo_client.echo(echo_value)
                    if echo_response == echo_value:
                        echo_check_passed = True
                        with open(self.output_file, 'a') as f:
                            f.write(f"ECHO check received response: {echo_response}\n")
                    else:
                        with open(self.output_file, 'a') as f:
                            f.write(f"ECHO check received unexpected response: {echo_response}\n")
                    echo_client.close()
                except redis.RedisError as e:
                    error_output += f"Error during separate ECHO check: {str(e)}\n"
                    with open(self.output_file, 'a') as f:
                        f.write(f"ECHO check error: {str(e)}\n")
                    # Keep echo_check_passed as False
                    
                # Log the ECHO result
                with open(self.output_file, 'a') as f:
                    f.write(f"ECHO check (separate connection): {'PASSED' if echo_check_passed else 'FAILED'}\n")
            
            
            # Execute commands - either in pipeline or individually
            results = []
            
            if self.use_pipeline:
                # Pipeline mode - execute all commands in a single transaction
                pipeline = redis_client.pipeline(transaction=False)
                
                # Check if we have any commands to execute
                if not commands:
                    # Log warning about empty command list
                    error_output += "Warning: No commands to execute in pipeline.\n"
                    with open(self.output_file, 'a') as f:
                        f.write("Warning: Pipeline has no commands to execute.\n")
                    
                    # Add some dummy commands to ensure pipeline is not empty
                    commands = [
                        "PING pipeline_test",
                        "INFO",
                        "TIME"
                    ]
                    
                    # Update log with dummy commands
                    with open(self.output_file, 'a') as f:
                        f.write("Adding default commands to pipeline:\n")
                        for cmd in commands:
                            f.write(f"  {cmd}\n")
                
                # Add all commands to the pipeline
                for cmd in commands:
                    try:
                        # Parse command into command name and arguments
                        cmd_parts = cmd.split()
                        if not cmd_parts:
                            continue
                            
                        command_name = cmd_parts[0].upper()
                        args = cmd_parts[1:]
                        
                        # Queue the command in the pipeline
                        pipeline.execute_command(command_name, *args)
                        
                        # Log that the command was queued in the pipeline
                        with open(self.output_file, 'a') as f:
                            f.write(f"Queued in pipeline: {command_name} {' '.join(args)}\n")
                            
                    except Exception as e:
                        error_output += f"Error queuing {cmd} in pipeline: {str(e)}\n"
                
                # Execute the pipeline and get responses
                try:
                    # Log that we're executing the pipeline
                    with open(self.output_file, 'a') as f:
                        f.write(f"Executing pipeline with {len(commands)} commands...\n")
                    
                    # The command_stack attribute holds the number of queued commands
                    # Check if anything was actually queued
                    if hasattr(pipeline, 'command_stack') and pipeline.command_stack:
                        with open(self.output_file, 'a') as f:
                            f.write(f"Pipeline has {len(pipeline.command_stack)} queued commands\n")
                    else:
                        with open(self.output_file, 'a') as f:
                            f.write("Warning: Pipeline appears to be empty! Re-queueing commands...\n")
                        
                        # Re-queue all commands explicitly
                        for cmd in commands:
                            cmd_parts = cmd.split()
                            if cmd_parts:
                                command_name = cmd_parts[0].upper()
                                args = cmd_parts[1:] if len(cmd_parts) > 1 else []
                                pipeline.execute_command(command_name, *args)
                                
                    # Execute the pipeline
                    responses = pipeline.execute()
                    
                    # In pipeline mode, just log all responses as a single entry
                    pipeline_result = "Pipeline executed with the following responses:\n"
                    
                    # Include ECHO check result from the separate connection
                    pipeline_result += f"ECHO check (separate connection): {'PASSED' if echo_check_passed else 'FAILED'}\n"
                    
                    # Add all responses in a single log entry
                    pipeline_result += f"Total commands in pipeline: {len(commands)}, Responses received: {len(responses)}\n\n"
                    
                    # Super robust handling of commands and responses
                    i = 0
                    response_i = 0
                    
                    # Print all commands
                    pipeline_result += "Commands sent:\n"
                    for i, cmd in enumerate(commands):
                        pipeline_result += f"Command [{i+1}]: {cmd}\n"
                    
                    pipeline_result += "\nResponses received:\n"
                    
                    # Print all responses without trying to match them to commands
                    for i, response in enumerate(responses):
                        try:
                            # Handle different response types safely
                            if isinstance(response, bytes):
                                try:
                                    resp_str = response.decode('utf-8')
                                    pipeline_result += f"Response [{i+1}]: {resp_str}\n"
                                except UnicodeDecodeError:
                                    # If we can't decode as UTF-8, show as hex
                                    pipeline_result += f"Response [{i+1}]: <binary data: {response.hex()[:60]}...>\n"
                            else:
                                # Just convert to string directly without any special handling
                                pipeline_result += f"Response [{i+1}]: {response}\n"
                        except Exception as e:
                            # Catch any possible error in handling responses
                            pipeline_result += f"Response [{i+1}]: <error displaying response: {str(e)}>\n"
                    
                    # Add to results as a single entry
                    results.append(pipeline_result)
                    
                except Exception as e:
                    # Catch absolutely any error and continue execution
                    error_type = type(e).__name__
                    error_message = str(e)
                    
                    if isinstance(e, UnicodeDecodeError):
                        error_output += f"Error with binary data in pipeline: {error_message}\n"
                        error_output += "Binary data is now handled safely in pipeline mode.\n"
                    elif isinstance(e, redis.RedisError):
                        error_output += f"Redis error in pipeline: {error_message}\n"
                    elif isinstance(e, TypeError) and "'int' object is not iterable" in error_message:
                        error_output += f"Type error with response: {error_message}\n"
                        error_output += "This may occur when a command returns an integer response.\n"
                    elif "too many values to unpack" in error_message:
                        error_output += f"Unpacking error: {error_message}\n"
                        error_output += "This may occur with certain Redis commands in pipeline mode.\n"
                    else:
                        error_output += f"Error executing pipeline ({error_type}): {error_message}\n"
                        
                    # Try to record as much info as possible about what happened
                    try:
                        error_output += f"Commands executed: {len(commands)}\n"
                        for i, cmd in enumerate(commands):
                            if i < 5:  # Just log the first 5 to avoid huge logs
                                error_output += f"  {i+1}. {cmd}\n"
                        if len(commands) > 5:
                            error_output += f"  ... and {len(commands) - 5} more commands\n"
                    except:
                        error_output += "Failed to log commands information.\n"
            else:
                # Normal mode - execute commands individually
                for cmd in commands:
                    try:
                        # Parse command into command name and arguments
                        cmd_parts = cmd.split()
                        if not cmd_parts:
                            continue
                            
                        command_name = cmd_parts[0].upper()
                        args = cmd_parts[1:]
                        
                        # Execute the command
                        response = redis_client.execute_command(command_name, *args)
                        
                        # Check if this is the ECHO command (in normal mode, should be the first command)
                        if command_name == "ECHO" and args and args[0] == echo_value:
                            if response == echo_value:
                                echo_check_passed = True
                        
                        results.append(f"Command: {cmd}\nResponse: {response}\n")
                    except redis.RedisError as e:
                        results.append(f"Command: {cmd}\nError: {str(e)}\n")
                        error_output += f"Error executing {cmd}: {str(e)}\n"
            
            # Combine all results
            result_output = "\n".join(results)
            
            # Close the Redis connection
            redis_client.close()
            
        except (redis.ConnectionError, redis.TimeoutError, socket.error) as e:
            exit_code = 1
            error_output = f"Connection error: {str(e)}"
            
        execution_time = time.time() - start_time
        
        # Log the outcome of this batch
        with open(self.output_file, 'a') as f:
            if exit_code != 0 or not echo_check_passed:
                f.write(f"EXECUTION FAILED (code {exit_code})\n")
                
                if not echo_check_passed:
                    if self.use_pipeline:
                        f.write("SERVER CHECK FAILED: Redis server did not respond to ECHO command on separate connection\n")
                        
                        # Write the ECHO check failure to the error log
                        echo_error_message = f"Batch {batch_num} FAILED (server did not respond to ECHO command on separate connection)"
                    else:
                        f.write("SERVER CHECK FAILED: Redis server did not respond to ECHO command\n")
                        
                        # Write the ECHO check failure to the error log
                        echo_error_message = f"Batch {batch_num} FAILED (server did not respond to ECHO command)"
                    
                    with open(self.error_log, 'a') as error_file:
                        error_file.write(f"\n==== BATCH {batch_num} ERROR ====\n")
                        error_file.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
                        error_file.write(f"{echo_error_message}\n")
                        error_file.write(f"The ECHO command did not receive the expected response: {echo_value}\n")
                        if result_output:
                            error_file.write("Command results received:\n")
                            error_file.write(result_output)
                            
                    exit_code = 1  # Force failure if echo check failed
                
                if exit_code == 124:
                    f.write(f"TIMEOUT: Redis server did not respond within {timeout_seconds} seconds\n")
                    
                if error_output:
                    f.write("ERRORS:\n")
                    f.write(error_output)
                    
                    # Write any other errors to the error log
                    with open(self.error_log, 'a') as error_file:
                        if not error_file.tell() or not echo_check_passed:
                            error_file.write(f"\n==== BATCH {batch_num} ERROR ====\n")
                            error_file.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
                        
                        # In pipeline mode, don't parse individual command errors
                        if not self.use_pipeline:
                            error_file.write("ERROR DETAILS:\n")
                            error_file.write(error_output)
                        else:
                            error_file.write("Pipeline execution error (details not parsed):\n")
                            error_file.write(error_output)
                    
                if result_output:
                    if self.use_pipeline:
                        f.write("PIPELINE RESULTS:\n")
                    else:
                        f.write("PARTIAL RESULTS:\n")
                    f.write(result_output)
                    
                with open(self.summary_log, 'a') as summary:
                    if not echo_check_passed:
                        summary.write(f"Batch {batch_num} FAILED (server did not respond to ECHO command)\n")
                    else:
                        summary.write(f"Batch {batch_num} FAILED (exit code: {exit_code})\n")
                    
                if self.verbose:
                    if not echo_check_passed:
                        print(f"Batch {batch_num} FAILED (server did not respond to ECHO command)")
                    else:
                        print(f"Batch {batch_num} FAILED (exit code: {exit_code})")
                    if exit_code == 124:
                        print("- Timeout occurred, server may be unresponsive")
                    elif error_output:
                        print(f"- Error: {error_output[:100]}...")
            else:
                if self.use_pipeline:
                    f.write(f"PIPELINE EXECUTION SUCCEEDED ({execution_time:.2f}s)\n")
                    f.write(f"SERVER CHECK: PASSED (ECHO response received on separate connection)\n")
                else:
                    f.write(f"EXECUTION SUCCEEDED ({execution_time:.2f}s)\n")
                    f.write(f"SERVER CHECK: PASSED (ECHO response received)\n")
                
                if result_output:
                    if self.use_pipeline:
                        f.write("PIPELINE RESULTS:\n")
                    else:
                        f.write("RESULTS:\n")
                    f.write(result_output)
                    
                if self.verbose:
                    if self.use_pipeline:
                        print(f"Pipeline batch {batch_num} succeeded ({execution_time*1000:.0f}ms)")
                    else:
                        print(f"Batch {batch_num} succeeded ({execution_time*1000:.0f}ms)")
                else:
                    # Print a progress indicator
                    if batch_num % 10 == 0 or batch_num == self.num_batches:
                        print(".", end="", flush=True)
                        if batch_num % 50 == 0 or batch_num == self.num_batches:
                            print(f" {batch_num}/{self.num_batches}")
                            
        # Wait a small random time between requests to avoid overwhelming the server
        time.sleep(random.randint(1, 5) / 10)
        
        # Return tuple of (success, echo_failed)
        # success = exit_code is 0 and echo check passed
        # echo_failed = echo check specifically failed
        return (exit_code == 0 and echo_check_passed, not echo_check_passed)
        
    def main(self):
        """Main execution function"""
        failed_batches = 0
        success_batches = 0
        consecutive_failures = 0  # Track consecutive failures separately
        consecutive_echo_failures = 0  # Track consecutive ECHO check failures
        max_consecutive_echo_failures = 5  # Maximum allowed consecutive ECHO failures
        
        print(f"Starting Redis command fuzzer with {self.num_batches} batches...")
        if self.fuzz_enabled:
            print("Fuzzing enabled: Commands will be randomly modified to test edge cases")
        print(f"Protocol version: RESP{3 if not self.protocol_resp2 else 2}")
        print(f"Pipeline mode: {'Enabled' if self.use_pipeline else 'Disabled'}")
            
        with open(self.summary_log, 'a') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Beginning execution of {self.num_batches} batches\n")
            f.write(f"Protocol version: RESP{3 if not self.protocol_resp2 else 2}\n")
            
        # Process each batch
        batch_num = 0
        for batch_num in range(1, self.num_batches + 1):
            batch_result = self.execute_batch(batch_num)
            
            # Check if this is an echo failure specifically
            if isinstance(batch_result, tuple) and len(batch_result) == 2:
                batch_succeeded, echo_failed = batch_result
            else:
                # For backward compatibility if execute_batch hasn't been updated yet
                batch_succeeded = batch_result
                echo_failed = not batch_succeeded  # Assume failure is due to echo check
                
            if not batch_succeeded:
                failed_batches += 1
                consecutive_failures += 1
                
                # Track echo check failures separately
                if echo_failed:
                    consecutive_echo_failures += 1
                    
                    # Check if we've reached the maximum allowed consecutive ECHO failures
                    if consecutive_echo_failures >= max_consecutive_echo_failures:
                        error_message = f"Error: {consecutive_echo_failures} consecutive ECHO check failures"
                        detail_message = f"The Redis server failed to respond to ECHO checks {consecutive_echo_failures} times in a row."
                        
                        # Print to console
                        print(error_message)
                        print(detail_message)
                        print(f"Halting execution after {batch_num} batches due to repeated ECHO failures.")
                        
                        # Log to summary file
                        with open(self.summary_log, 'a') as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {error_message}\n")
                            f.write(f"Halting execution after {batch_num} out of {self.num_batches} batches.\n")
                            f.write(f"{detail_message}\n")
                        
                        # Log to error file
                        with open(self.error_log, 'a') as error_file:
                            error_file.write(f"\n==== CONSECUTIVE ECHO FAILURES ====\n")
                            error_file.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
                            error_file.write(f"After Batch: {batch_num}\n")
                            error_file.write(f"{error_message}\n")
                            error_file.write(f"{detail_message}\n")
                            error_file.write(f"Stopping execution due to repeated ECHO check failures.\n")
                            
                        break
                
                # If we have 3 consecutive failures, check connectivity
                if consecutive_failures >= 3:
                    print("Multiple consecutive failures. Checking Redis server...")
                    
                    try:
                        # Use Redis Python client to check connectivity
                        redis_client = redis.Redis(
                            host=self.ip, 
                            port=self.port, 
                            socket_timeout=2,
                            socket_connect_timeout=2,
                            protocol=2 if self.protocol_resp2 else 3  # Set protocol version based on args
                        )
                        ping_result = redis_client.ping()
                        redis_client.close()
                        
                        if not ping_result:
                            raise redis.ConnectionError("Ping returned False")
                            
                    except (redis.ConnectionError, redis.TimeoutError, socket.error) as e:
                        error_message = f"Error: Lost connection to Redis server at {self.ip}:{self.port}"
                        detail_message = f"Connection failure details: {str(e)}"
                        
                        # Print to console
                        print(error_message)
                        print(detail_message)
                        
                        # Log to summary file
                        with open(self.summary_log, 'a') as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Lost connection to Redis server after {batch_num} batches\n")
                            f.write(f"Details: {str(e)}\n")
                        
                        # Log to error file
                        with open(self.error_log, 'a') as error_file:
                            error_file.write(f"\n==== CONNECTION FAILURE ====\n")
                            error_file.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
                            error_file.write(f"After Batch: {batch_num}\n")
                            error_file.write(f"{error_message}\n")
                            error_file.write(f"{detail_message}\n")
                            error_file.write(f"Consecutive failures: {consecutive_failures}\n")
                            
                        break
            else:
                success_batches += 1
                consecutive_failures = 0  # Reset consecutive failures counter
                consecutive_echo_failures = 0  # Reset consecutive echo failures counter
                
        # Print summary
        print()
        print("Execution completed:")
        print(f"- Total batches: {batch_num}")
        print(f"- Successful batches: {success_batches}")
        print(f"- Failed batches: {failed_batches}")
        
        # Record summary
        with open(self.summary_log, 'a') as f:
            f.write("\n====================================\n")
            f.write("Execution Statistics:\n")
            f.write(f"- Total batches executed: {batch_num}\n")
            f.write(f"- Successful batches: {success_batches}\n")
            f.write(f"- Failed batches: {failed_batches}\n")
            
            if failed_batches > 0:
                failure_rate = (failed_batches * 100) / batch_num
                f.write(f"- Failure rate: {failure_rate:.2f}%\n")
            else:
                f.write("- Failure rate: 0%\n")
                
            # Record consecutive echo failures if execution stopped due to them
            if consecutive_echo_failures >= max_consecutive_echo_failures:
                f.write(f"\nExecution stopped after {consecutive_echo_failures} consecutive ECHO check failures\n")
                f.write(f"Maximum allowed consecutive ECHO failures: {max_consecutive_echo_failures}\n")
                
        print("Logs saved to:")
        print(f"  - Commands: {self.output_file}")
        print(f"  - Errors: {self.error_log}")
        print(f"  - Summary: {self.summary_log}")

    def print_usage(self):
        """Print usage instructions"""
        # Let argparse handle the regular help output
        # Only show the custom help when explicitly called
        pass

if __name__ == "__main__":
    fuzzer = RedisFuzzer()
    try:
        fuzzer.parse_arguments()
        fuzzer.setup_logging()
        fuzzer.test_redis_connectivity()
        fuzzer.main()
        fuzzer.cleanup(0)
    except Exception as e:
        print(f"Error: {e}")
        fuzzer.cleanup(1)
