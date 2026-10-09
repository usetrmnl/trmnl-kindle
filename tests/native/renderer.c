/* Stand in for eips during tests: check open files, then return or wait. */
#define _GNU_SOURCE
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    FILE *f = fopen(getenv("TRACE"), "a");
    if (!f) return 90;
    fprintf(f, "%ld draw\n", (long)getpid()); fflush(f);
    DIR *dir = opendir("/proc/self/fd"); struct dirent *de;
    if (!dir) return 91;
    while ((de = readdir(dir))) {
        char path[300], target[1024];
        snprintf(path, sizeof path, "/proc/self/fd/%s", de->d_name);
        ssize_t len = readlink(path, target, sizeof target-1);
        if (len >= 0) {
            target[len] = 0;
            if (!strcmp(target, getenv("INPUT"))) {
                fprintf(f, "%ld leaked-input\n", (long)getpid()); fclose(f); return 92;
            }
        }
    }
    closedir(dir);
    if (argc != 3 || strcmp(argv[1], "-g")) return 93;
    if (getenv("DRAW_DELAY_US")) usleep(atoi(getenv("DRAW_DELAY_US")));
    if (getenv("DRAW_BLOCK")) { for (;;) pause(); }
    if (getenv("DRAW_FAIL")) return 1;
    fprintf(f, "%ld draw-done\n", (long)getpid()); fclose(f);
    return 0;
}
