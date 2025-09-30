#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <string.h>

#include <whereami.h>

using namespace std;

int main(int argc, char** argv) {
    auto self_length = wai_getExecutablePath(NULL, 0, NULL);
    auto self_path_cstr = static_cast<char*>(malloc(self_length + 1));
    wai_getExecutablePath(self_path_cstr, self_length, NULL);
    self_path_cstr[self_length] = '\0';

    auto conf_path = filesystem::path(self_path_cstr);
    conf_path.replace_extension(".path.txt");
    
    string exec_path_string;
    ifstream conf;
    conf.open(conf_path);
    if (!conf) {
        cerr << argv[0] << ": Can't open config file: \"" << conf_path.string() << "\"\n";
        return 1;
    }
    getline(conf, exec_path_string);
    conf.close();

    auto exec_path = filesystem::path(exec_path_string);
    auto exec_path_new = exec_path;
    if (exec_path.is_relative()) {
        exec_path_new = filesystem::path(self_path_cstr).parent_path();
        exec_path_new /= exec_path;
    }
    
    free(self_path_cstr);
    self_path_cstr = NULL;

    string args;

#if defined(_WIN32) || defined(WIN32)
    args += "\"";
#endif

    args += "\"";
    args += exec_path_new.string();
    args += "\"";

    for (int i = 1; i < argc; ++i) {
        args += " ";

        if (strcmp(argv[i], "-") == 0) {
            args += "\"-i\" \"";
            args += argv[i];
            args += "\"";
        }
        else if (strcmp(argv[i], "--output") == 0) {
            args += "\"-b\"";
        }
        else if (strcmp(argv[i], "--photon-noise-table") == 0) {
            args += "\"--fgs-table\"";
        }
        else if (strcmp(argv[i], "-y") == 0);
        else {
            args += "\"";
            args += argv[i];
            args += "\"";
        }
    }

#if defined(_WIN32) || defined(WIN32)
    args += "\"";
#endif

#ifndef NDEBUG
    cerr << args << "\n";
#endif

    cout.flush();
    cerr.flush();
    system(args.c_str());

    return 0;
}
