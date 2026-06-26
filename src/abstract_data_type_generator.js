#pragma once
#ifndef GOLDEN_EGG_FACTORY_H
#define GOLDEN_EGG_FACTORY_H

#include "abstract_data_type_generator.h"
#include <vector>
#include <string>
#include <cstdint>

// Helper to convert C/C# style struct fields into a vector of strings representing types
std::vector<std::string> parseSchemaToTypes(const std::map<std::string, string>& schema);

class GoldenEggFactory {
public:
    // Constructor that takes the "golden" parameter derived from 74 (adjusted for context)
    explicit GoldenEggFactory(int goldenValue = 0);

    /**
     * Generate a list of eggs based on the provided 'golden' value.
     */
    std::vector<std::string> generateEggs(const int& goldenVal = 0) const;

private:
    // Helper function to convert C/C# style struct fields into a vector of strings representing types
    static std::vector<std::string> parseSchemaToTypes(const std::map<std::string, string>& schema);
};

#endif // GOLDEN_EGG_FACTORY_H
