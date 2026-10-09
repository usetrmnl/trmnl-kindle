/* SPDX-License-Identifier: MIT
 * Read one exit gesture while keeping it out of the Kindle UI. See README.md.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Keep the Kindle input record layout independent of library and header versions. */
struct wire_event { uint32_t sec, usec; uint16_t type, code; int32_t value; };
_Static_assert(sizeof(struct wire_event) == 16, "ARM32 input record");
_Static_assert(offsetof(struct wire_event, type) == 8, "type offset");
_Static_assert(offsetof(struct wire_event, code) == 10, "code offset");
_Static_assert(offsetof(struct wire_event, value) == 12, "value offset");
#define KEY_BYTES ((KEY_MAX + 8) / 8)
enum result {
    RESULT_CONFIRMED, RESULT_TIMEOUT, RESULT_GRAB_FAILED, RESULT_STATE_ERROR,
    RESULT_DROPPED, RESULT_READER_ERROR, RESULT_PROMPT_ERROR, RESULT_SIGNAL,
    RESULT_HELD, RESULT_UNAVAILABLE, RESULT_BUSY_INPUT
};
struct gesture {
    unsigned char keys[KEY_BYTES];
    int armed, pending, up_seen, complete;
};
static void put_bit(unsigned char *keys, unsigned key, int value)
{
    if (value) keys[key / 8] |= 1u << (key % 8);
    else keys[key / 8] &= ~(1u << (key % 8));
}
static int neutral(const unsigned char *keys)
{
    for (size_t i = 0; i < KEY_BYTES; i++) if (keys[i]) return 0;
    return 1;
}
/* Button mode accepts ordinary keyboard codes, never power-management keys. */
static int allowed_key(unsigned key, unsigned selected)
{
    return selected ? key == selected : key > KEY_RESERVED && key < BTN_MISC &&
        key != KEY_POWER && key != KEY_SLEEP && key != KEY_WAKEUP && key != KEY_SUSPEND;
}
static int consume_event(struct gesture *g, const struct wire_event *e, unsigned selected)
{
    if (e->type == EV_SYN && e->code == SYN_DROPPED) return RESULT_DROPPED;
    if (e->type == EV_KEY) {
        if (e->code > KEY_MAX || e->value < 0 || e->value > 2) return RESULT_READER_ERROR;
        if (e->value != 2) put_bit(g->keys, e->code, e->value);
        if (e->value == 1) {
            g->complete = 0;
            if (allowed_key(e->code, selected) && g->armed) {
                g->pending = e->code;
                g->up_seen = 0;
                g->armed = 0;
            }
        } else if (e->value == 0 && g->pending && e->code == g->pending) {
            g->up_seen = 1;
        }
    } else if (e->type == EV_SYN && e->code == SYN_REPORT) {
        if (neutral(g->keys)) {
            if (g->pending && g->up_seen) g->complete = 1;
            g->pending = g->up_seen = 0;
            g->armed = 1;
        } else if (!g->pending) g->armed = 0;
    }
    return 0;
}

#ifndef EXIT_EIPS_PATH
#define EXIT_EIPS_PATH "/usr/sbin/eips"
#endif
#ifdef EXIT_INPUT_TEST
enum { RENDER_MS = 300, WINDOW_MS = 700, DRAIN_MS = 200 };
#else
enum { RENDER_MS = 5000, WINDOW_MS = 10000, DRAIN_MS = 2000 };
#endif
static volatile sig_atomic_t cancelled;
static int key_bytes;
static void cancel(int sig) { (void)sig; cancelled = 1; }
static int64_t now_ms(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static int bit(const unsigned char *keys, unsigned key)
{
    return (keys[key / 8] >> (key % 8)) & 1;
}
static int key_state(int fd, unsigned char *keys)
{
    memset(keys, 0, KEY_BYTES);
    return ioctl(fd, EVIOCGKEY(KEY_BYTES), keys) >= key_bytes ? 0 : -1;
}
/* Read up to capacity events; zero means none are ready, not end of file. */
static int events(int fd, struct wire_event *batch, size_t capacity)
{
    ssize_t n = read(fd, batch, capacity * sizeof *batch);
    if (n < 0 && (errno == EAGAIN || errno == EINTR)) return 0;
    if (n <= 0 || n % sizeof *batch) return -1;
    return (int)(n / sizeof *batch);
}
static int poll_input(int fd, int64_t deadline)
{
    int64_t now = now_ms();
    if (now < 0) return -1;
    if (now >= deadline) return 0;
    struct pollfd p = {.fd = fd, .events = POLLIN};
    int rc = poll(&p, 1, (int)(deadline - now));
    if (rc < 0 && errno == EINTR) return 0;
    if (rc < 0 || (p.revents & (POLLERR | POLLHUP | POLLNVAL))) return -1;
    return rc;
}
static void reap_renderer(pid_t pid, int kill_first)
{
    if (kill_first) kill(pid, SIGKILL);
    /* Kill and wait for the child; a stuck kernel call can still delay its exit. */
    while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {}
}
static int render(int input_fd, const char *image)
{
    int64_t start = now_ms();
    if (start < 0) return RESULT_STATE_ERROR;
    pid_t owner = getpid();
    pid_t pid = fork();
    if (pid < 0) return RESULT_PROMPT_ERROR;
    if (pid == 0) {
        close(input_fd); /* CLOEXEC also covers exec; never ungrab in child. */
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != owner) _exit(1);
        execl(EXIT_EIPS_PATH, "eips", "-g", image, (char *)NULL);
        _exit(1);
    }
    for (;;) {
        int status;
        pid_t rc = waitpid(pid, &status, WNOHANG);
        if (rc == pid) {
            int64_t now = now_ms();
            return !cancelled && now >= 0 && now - start < RENDER_MS &&
                WIFEXITED(status) && WEXITSTATUS(status) == 0
                ? 0 : (cancelled ? RESULT_SIGNAL : RESULT_PROMPT_ERROR);
        }
        if (rc < 0 && errno != EINTR) { reap_renderer(pid, 1); return RESULT_PROMPT_ERROR; }
        int64_t now = now_ms();
        if (cancelled || now < 0 || now - start >= RENDER_MS) {
            reap_renderer(pid, 1);
            return cancelled ? RESULT_SIGNAL : RESULT_PROMPT_ERROR;
        }
        int remaining = (int)(start + RENDER_MS - now);
        poll(NULL, 0, remaining < 10 ? remaining : 10);
    }
}
/* Wait for release without accepting another gesture.
 * If we close while input is held, its later release can reach the Kindle UI. */
static int settle(int fd, int reason, int in_packet)
{
    struct wire_event batch[64];
    unsigned char keys[KEY_BYTES];
    int64_t start = now_ms();
    if (start < 0) return RESULT_STATE_ERROR;
    for (;;) {
        int n = events(fd, batch, 64);
        if (n < 0) return RESULT_READER_ERROR;
        for (int i = 0; i < n; i++)
            in_packet = !(batch[i].type == EV_SYN && batch[i].code == SYN_REPORT);
        if (key_state(fd, keys)) return RESULT_STATE_ERROR;
        if (n == 0 && !in_packet && neutral(keys)) return reason;
        int64_t now = now_ms();
        if (now < 0) return RESULT_STATE_ERROR;
        if (now - start >= DRAIN_MS)
            return reason == RESULT_TIMEOUT ? RESULT_HELD : reason;
        if (n == 0 && poll_input(fd, start + DRAIN_MS) < 0) return RESULT_READER_ERROR;
    }
}
static int listen_window(int fd, unsigned selected, int64_t start)
{
    struct wire_event batch[64];
    struct gesture g = {0};
    unsigned char keys[KEY_BYTES];
    int in_packet = 0, discarding = 1;
    int64_t deadline = start + WINDOW_MS;
    for (;;) {
        int64_t now = now_ms();
        if (now < 0) return RESULT_STATE_ERROR;
        if (cancelled) return settle(fd, RESULT_SIGNAL, in_packet);
        if (now >= deadline) return settle(fd, RESULT_TIMEOUT, in_packet);
        int n = events(fd, batch, 64);
        if (n < 0) return RESULT_READER_ERROR;
        for (int i = 0; i < n; i++) {
            in_packet = !(batch[i].type == EV_SYN && batch[i].code == SYN_REPORT);
            int result = consume_event(&g, &batch[i], selected);
            if (result == RESULT_DROPPED) return settle(fd, result, 1);
            if (result) return result;
        }
        now = now_ms(); /* Check time again after processing events. */
        if (now < 0) return RESULT_STATE_ERROR;
        if (cancelled) return settle(fd, RESULT_SIGNAL, in_packet);
        if (now >= deadline) return settle(fd, RESULT_TIMEOUT, in_packet);
        if (n) continue; /* Empty the queue so a later dropped-event report is not missed. */
        if (discarding) {
            if (key_state(fd, g.keys)) return RESULT_STATE_ERROR;
            g.armed = neutral(g.keys) && !in_packet;
            g.pending = g.up_seen = g.complete = 0;
            discarding = 0;
        } else if (g.complete && !in_packet && neutral(g.keys)) {
            if (key_state(fd, keys)) return RESULT_STATE_ERROR;
            now = now_ms();
            if (now < 0) return RESULT_STATE_ERROR;
            if (cancelled) return settle(fd, RESULT_SIGNAL, in_packet);
            if (now >= deadline) return settle(fd, RESULT_TIMEOUT, in_packet);
            if (neutral(keys)) return RESULT_CONFIRMED;
            /* New input arrived during the state check; keep exclusive access until release. */
            memcpy(g.keys, keys, KEY_BYTES);
            g.armed = g.pending = g.up_seen = g.complete = 0;
        }
        if (poll_input(fd, deadline) < 0) return RESULT_READER_ERROR;
    }
}
static int acquire_and_listen(int fd, unsigned selected, const char *image)
{
    unsigned char caps[KEY_BYTES] = {0}, keys[KEY_BYTES];
    struct wire_event batch[64], extra;
    struct stat st;
    if (fstat(fd, &st) || !S_ISCHR(st.st_mode)) return RESULT_UNAVAILABLE;
    key_bytes = ioctl(fd, EVIOCGBIT(EV_KEY, sizeof caps), caps);
    if (key_bytes <= 0 || key_bytes > KEY_BYTES || bit(caps, KEY_POWER) ||
        bit(caps, KEY_SLEEP) || bit(caps, KEY_WAKEUP) || bit(caps, KEY_SUSPEND)) return RESULT_UNAVAILABLE;
    int supported = 0;
    for (unsigned key = 1; key < (unsigned)key_bytes * 8; key++)
        if (bit(caps, key) && allowed_key(key, selected)) supported = 1;
    if (!supported) return RESULT_UNAVAILABLE;
    if (key_state(fd, keys)) return RESULT_STATE_ERROR;
    if (!neutral(keys)) return RESULT_BUSY_INPUT;
    if (cancelled) return RESULT_SIGNAL;
    if (ioctl(fd, EVIOCGRAB, (void *)1)) return RESULT_GRAB_FAILED;
    /* Discard events queued before the grab; give up if one batch cannot clear them. */
    int n = events(fd, batch, 64);
    if (n < 0) return RESULT_READER_ERROR;
    for (int i = 0; i < n; i++)
        if (batch[i].type == EV_SYN && batch[i].code == SYN_DROPPED) return RESULT_DROPPED;
    if (events(fd, &extra, 1) != 0) return RESULT_BUSY_INPUT;
    if (n && !(batch[n-1].type == EV_SYN && batch[n-1].code == SYN_REPORT))
        return RESULT_BUSY_INPUT;
    if (key_state(fd, keys)) return RESULT_STATE_ERROR;
    if (!neutral(keys)) return RESULT_BUSY_INPUT;
    if (cancelled) return RESULT_SIGNAL;
    int rc = render(fd, image);
    if (rc) return settle(fd, rc, 0);
    int64_t start = now_ms();
    if (start < 0) return RESULT_STATE_ERROR;
    return listen_window(fd, selected, start);
}
int main(int argc, char **argv)
{
#if !defined(EXIT_INPUT_TEST) && !(defined(__arm__) && __SIZEOF_POINTER__ == 4 && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
    (void)argc; (void)argv;
    return RESULT_UNAVAILABLE;
#else
    if (argc == 2 && !strcmp(argv[1], "--check")) return 0;
    if (argc != 4) return RESULT_UNAVAILABLE;
    char *end;
    unsigned long key = strtoul(argv[2], &end, 10);
    if (!*argv[2] || *end || !(key == BTN_TOUCH || key == 0))
        return RESULT_UNAVAILABLE;
    struct sigaction action = {.sa_handler = cancel};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, NULL) || sigaction(SIGINT, &action, NULL) ||
        sigaction(SIGHUP, &action, NULL)) return RESULT_STATE_ERROR;
    pid_t parent = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGTERM)) return RESULT_STATE_ERROR;
    if (getppid() != parent || parent == 1) cancelled = 1;
    if (cancelled) return RESULT_SIGNAL;
    int fd = open(argv[1], O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return RESULT_UNAVAILABLE;
    int flags = fcntl(fd, F_GETFD);
    if (flags < 0 || fcntl(fd, F_SETFD, flags | FD_CLOEXEC)) {
        close(fd); return RESULT_STATE_ERROR;
    }
    int result = acquire_and_listen(fd, (unsigned)key, argv[3]);
    close(fd); /* Closing returns input to other programs; consumed events are not replayed. */
    return cancelled ? RESULT_SIGNAL : result;
#endif
}
