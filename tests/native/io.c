/* Replace device operations for tests; keep real pipes and processes. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static int input_fd = -1;
static unsigned key_queries;
int __real_open(const char *, int, ...);
int __real_close(int);
int __real_fstat(int, struct stat *);
void trace(const char *what)
{
    FILE *f = fopen(getenv("TRACE"), "a");
    if (!f) _exit(90);
    fprintf(f, "%ld %s\n", (long)getpid(), what);
    fclose(f);
}
int __wrap_open(const char *path, int flags, ...)
{
    if (strcmp(path, getenv("INPUT"))) { errno = EACCES; return -1; }
    if (getenv("OPEN_FAIL")) { errno = EACCES; return -1; }
    input_fd = __real_open(path, (flags & ~O_ACCMODE) | O_RDWR);
    trace("open");
    return input_fd;
}
int __wrap_fstat(int fd, struct stat *st)
{
    int rc = __real_fstat(fd, st);
    if (rc == 0 && fd == input_fd && !getenv("NOT_CHAR"))
        st->st_mode = (st->st_mode & ~S_IFMT) | S_IFCHR;
    return rc;
}
int __wrap_close(int fd)
{
    if (fd == input_fd) { trace("close-input"); input_fd = -1; }
    return __real_close(fd);
}
int __wrap_ioctl(int fd, unsigned long request, ...)
{
    (void)fd;
    va_list ap; va_start(ap, request); void *arg = va_arg(ap, void *); va_end(ap);
    unsigned char *bits = arg;
    if (request == EVIOCGRAB) {
        trace(arg ? "grab" : "ungrab");
        if (getenv("GRAB_FAIL")) { errno = EBUSY; return -1; }
        return 0;
    }
    if (_IOC_NR(request) == _IOC_NR(EVIOCGBIT(EV_KEY, 0))) {
        unsigned key = getenv("KEY") ? atoi(getenv("KEY")) : 330;
        if (!key) {
            for (unsigned k = 1; k < 256; k++)
                if (k != KEY_POWER && k != KEY_SLEEP && k != KEY_WAKEUP && k != KEY_SUSPEND)
                    bits[k/8] |= 1u << (k%8);
        } else bits[key/8] |= 1u << (key%8);
        if (getenv("POWER_NODE")) {
            unsigned power = atoi(getenv("POWER_NODE"));
            bits[power/8] |= 1u << (power%8);
        }
        return _IOC_SIZE(request);
    }
    if (_IOC_NR(request) == _IOC_NR(EVIOCGBIT(0, 0))) {
        bits[0] = 3; return _IOC_SIZE(request);
    }
    if (_IOC_NR(request) == _IOC_NR(EVIOCGKEY(0))) {
        trace("keys"); key_queries++;
        if (getenv("KEYS_DELAY_AT") && key_queries == (unsigned)atoi(getenv("KEYS_DELAY_AT")))
            usleep(200000);
        if (getenv("KEYS_FAIL") && key_queries >= (unsigned)atoi(getenv("KEYS_FAIL"))) {
            errno = EIO; return -1;
        }
        FILE *f = fopen(getenv("STATE"), "rb");
        if (!f) return -1;
        size_t n = fread(bits, 1, _IOC_SIZE(request), f); fclose(f);
        return (int)n;
    }
    errno = EINVAL; return -1;
}
