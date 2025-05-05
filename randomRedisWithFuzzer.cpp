# apt-get install libhiredis-dev g++
# g++ fuzzer.cpp -o fuzzer -I/usr/local/include/hiredis -lhiredis
# ./fuzzer 127.0.0.1:6379 5000 /root/randomRedisCommands.txt

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstdlib>
#include <ctime>
#include <chrono>
#include <random>
#include <algorithm>
#include <sstream>
#include <cstring>
#include <unistd.h>
#include <hiredis/hiredis.h>

// Function to read a specific line from a file
std::string readLineFromFile(const std::string& filePath, int lineNum) {
    std::ifstream file(filePath);
    std::string line;
    int currentLine = 0;
    
    while (std::getline(file, line) && currentLine < lineNum) {
        currentLine++;
    }
    
    return line;
}

// Function to count lines in a file
int countFileLines(const std::string& filePath) {
    std::ifstream file(filePath);
    int lineCount = 0;
    std::string line;
    
    while (std::getline(file, line)) {
        lineCount++;
    }
    
    return lineCount;
}

// Function to generate a random command from the commands file
std::string randomCommand(const std::string& commandsFile, int fileLength) {
    int lineNum = rand() % fileLength;
    return readLineFromFile(commandsFile, lineNum);
}

// Function to fuzz a command by adding a random special character
std::string fuzzCommand(const std::string& command, bool fuzzEnabled) {
    if (!fuzzEnabled) {
        return command;
    }
    
    std::string specialChars = "!@#$%^&*()_-+=<>?/";
    int randIndex = rand() % command.length();
    int randSpecialIndex = rand() % specialChars.length();
    char specialChar = specialChars[randSpecialIndex];
    
    std::string fuzzedCommand = command;
    fuzzedCommand.insert(randIndex, 1, specialChar);
    
    return fuzzedCommand;
}

// Function to create a unique temporary file
std::string createTempFile() {
    char tempFileName[] = "/tmp/redis-commands-XXXXXX";
    int fd = mkstemp(tempFileName);
    if (fd == -1) {
        std::cerr << "Error creating temporary file" << std::endl;
        exit(1);
    }
    close(fd);
    return std::string(tempFileName);
}

// Function to create a unique output file with timestamp
std::string createOutputFile() {
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    std::tm* now_tm = std::localtime(&now_time);
    
    char timestamp[20];
    std::strftime(timestamp, sizeof(timestamp), "%Y%m%d%H%M%S", now_tm);
    
    std::string outputFile = "/tmp/redis-commands-" + std::string(timestamp) + ".log";
    std::cout << "The OUTPUT filename is - " << outputFile << std::endl;
    
    return outputFile;
}

int main(int argc, char* argv[]) {
    // Check for correct usage
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <IP:PORT> <numOfBatches> [<commandsFilePath>] [<protocolVersion>] [--fuzz]" << std::endl;
        return 1;
    }
    
    // Parse IP and port
    std::string ipPort = argv[1];
    size_t colonPos = ipPort.find(':');
    if (colonPos == std::string::npos) {
        std::cerr << "Invalid IP:PORT format" << std::endl;
        return 1;
    }
    
    std::string ip = ipPort.substr(0, colonPos);
    int port = std::stoi(ipPort.substr(colonPos + 1));
    
    // Parse number of batches
    int numBatches = std::stoi(argv[2]);
    
    // Parse optional arguments
    std::string commandsFile = (argc > 3) ? argv[3] : "/root/redisCommands30.txt";
    std::string protocolVersion = (argc > 4) ? argv[4] : "-2";
    
    // Check if fuzzing is enabled
    bool fuzzEnabled = false;
    for (int i = 1; i < argc; i++) {
        if (std::string(argv[i]) == "--fuzz") {
            fuzzEnabled = true;
            break;
        }
    }
    
    // Seed random number generator
    srand(static_cast<unsigned int>(time(nullptr)));
    
    // Create temporary file and output file
    std::string tempFileName = createTempFile();
    std::string outputFileName = createOutputFile();
    
    // Count lines in commands file
    int fileLength = countFileLines(commandsFile);
    if (fileLength == 0) {
        std::cerr << "Error: Commands file is empty or cannot be read" << std::endl;
        return 1;
    }
    
    // Connect to Redis
    struct timeval timeout = {1, 0}; // 1 second timeout
    redisContext* context = redisConnectWithTimeout(ip.c_str(), port, timeout);
    if (context == nullptr || context->err) {
        if (context) {
            std::cerr << "Connection error: " << context->errstr << std::endl;
            redisFree(context);
        } else {
            std::cerr << "Connection error: can't allocate redis context" << std::endl;
        }
        return 1;
    }
    
    // Main loop
    for (int batchNum = 1; batchNum <= numBatches; batchNum++) {
        // Clear the temporary file
        std::ofstream tempFile(tempFileName, std::ios::trunc);
        if (!tempFile) {
            std::cerr << "Error opening temporary file for writing" << std::endl;
            redisFree(context);
            return 1;
        }
        
        // Generate random pipeline size
        int pipelineSize = (rand() % 10) + 1;
        
        // Generate and write commands to temporary file
        std::vector<std::string> commands;
        for (int i = 0; i < pipelineSize; i++) {
            std::string cmd = randomCommand(commandsFile, fileLength);
            std::string fuzzedCmd = fuzzCommand(cmd, fuzzEnabled);
            tempFile << fuzzedCmd << std::endl;
            commands.push_back(fuzzedCmd);
        }
        
        // Add PING command
        std::string pingCmd = "PING " + std::to_string(port);
        tempFile << pingCmd << std::endl;
        commands.push_back(pingCmd);
        
        tempFile.close();
        
        // Execute commands using Redis pipeline
        for (const auto& cmd : commands) {
            redisAppendCommand(context, cmd.c_str());
        }
        
        // Get replies
        redisReply* reply = nullptr;
        bool success = true;
        
        for (size_t i = 0; i < commands.size(); i++) {
            if (redisGetReply(context, (void**)&reply) != REDIS_OK) {
                std::cerr << "Error: Failed to execute commands on Redis server" << std::endl;
                success = false;
                break;
            }
            
            // Free the reply object
            if (reply != nullptr) {
                freeReplyObject(reply);
            }
        }
        
        if (!success) {
            redisFree(context);
            return 1;
        }
        
        // Append the commands to the output file
        std::ofstream outputFile(outputFileName, std::ios::app);
        if (!outputFile) {
            std::cerr << "Error opening output file for writing" << std::endl;
            redisFree(context);
            return 1;
        }
        
        outputFile << "\nBATCH NUMBER - " << batchNum << std::endl;
        
        // Read and write the commands from the temporary file
        std::ifstream readTempFile(tempFileName);
        std::string line;
        while (std::getline(readTempFile, line)) {
            outputFile << line << std::endl;
        }
        
        outputFile.close();
    }
    
    // Clean up
    redisFree(context);
    std::remove(tempFileName.c_str());
    
    return 0;
}
