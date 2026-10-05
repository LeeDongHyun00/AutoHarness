// Converts a JSON schema with llama.cpp's own converter and checks sample
// outputs against the resulting grammar. Usage: gcheck schema.json ok:a.json fail:b.txt ...
#include "json-schema-to-grammar.h"
#include "llama-grammar.h"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>

static std::string read_file(const std::string & path) {
    std::ifstream f(path);
    std::stringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

int main(int argc, char ** argv) {
    std::string gbnf;
    try {
        gbnf = json_schema_to_grammar(common_json::parse(read_file(argv[1])));
    } catch (const std::exception & e) {
        std::cerr << "CONVERSION FAILED: " << e.what() << "\n";
        return 2;
    }
    std::ofstream(std::string(argv[1]) + ".gbnf") << gbnf;
    std::cout << "grammar: " << gbnf.size() << " bytes\n";
    int mismatches = 0;
    for (int i = 2; i < argc; i++) {
        std::string spec = argv[i];
        bool expect_ok = spec.rfind("ok:", 0) == 0;
        std::string path = spec.substr(spec.find(':') + 1);
        llama_grammar * g = llama_grammar_init_impl(nullptr, gbnf.c_str(), "root", false, nullptr, 0, nullptr, 0);
        if (!g) {
            std::cerr << "GRAMMAR PARSE FAILED\n";
            return 3;
        }
        bool accepted;
        try {
            llama_grammar_accept_str(*g, read_file(path));
            accepted = std::any_of(g->stacks.begin(), g->stacks.end(), [](const auto & s) { return s.empty(); });
        } catch (const std::exception &) {
            accepted = false;
        }
        std::cout << (accepted ? "accepted " : "rejected ") << path << (accepted == expect_ok ? "" : "  <-- UNEXPECTED") << "\n";
        mismatches += accepted != expect_ok;
        llama_grammar_free_impl(g);
    }
    return mismatches ? 1 : 0;
}
