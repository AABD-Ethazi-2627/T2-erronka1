/* Test-only syscall fault injection. Never copied to the final image.
 * Only the exact fresh /tmp/cnc-del-* target configured by the test is affected.
 * No permissions, file descriptor limits or host files are changed. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static char generation[256];
static int attempts;
static int fault(const char *p, const char *op) {
  const char *target = getenv("CNC_DEL_TARGET"), *kind = getenv("CNC_DEL_OPERATION");
  const char *id = getenv("CNC_DEL_GENERATION"), *log = getenv("CNC_DEL_LOG");
  if (!target || !kind || !id || !log || strncmp(target, "/tmp/cnc-del-", 13) || strcmp(p, target) || strcmp(kind, op)) return 0;
  pthread_mutex_lock(&lock);
  if (strcmp(id, generation)) { snprintf(generation, sizeof generation, "%s", id); attempts = 0; }
  int count = atoi(getenv("CNC_DEL_COUNT") ? getenv("CNC_DEL_COUNT") : "0");
  int error = atoi(getenv("CNC_DEL_ERRNO") ? getenv("CNC_DEL_ERRNO") : "0");
  int inject = count < 0 || attempts < count;
  attempts++;
  char line[64]; int n = snprintf(line, sizeof line, "%s:%d\n", op, inject ? error : 0);
  int fd = syscall(SYS_openat, AT_FDCWD, log, O_WRONLY | O_CREAT | O_APPEND, 0600);
  if (fd >= 0) { syscall(SYS_write, fd, line, n); syscall(SYS_close, fd); }
  pthread_mutex_unlock(&lock);
  return inject ? error : 0;
}
int unlink(const char *p) {
  int e = fault(p, "unlink"); if (e) { errno = e; return -1; }
  int (*real)(const char *) = dlsym(RTLD_NEXT, "unlink"); return real(p);
}
int rmdir(const char *p) {
  int e = fault(p, "rmdir"); if (e) { errno = e; return -1; }
  int (*real)(const char *) = dlsym(RTLD_NEXT, "rmdir"); return real(p);
}
int remove(const char *p) {
  const char *op = getenv("CNC_DEL_OPERATION");
  int e = op ? fault(p, op) : 0; if (e) { errno = e; return -1; }
  int (*real)(const char *) = dlsym(RTLD_NEXT, "remove"); return real(p);
}
int unlinkat(int dirfd, const char *p, int flags) {
  char absolute[4096], link[64];
  const char *target = p;
  if (p[0] != '/') {
    if (dirfd == AT_FDCWD) snprintf(link, sizeof link, "/proc/self/cwd");
    else snprintf(link, sizeof link, "/proc/self/fd/%d", dirfd);
    ssize_t n = readlink(link, absolute, sizeof absolute - 2);
    if (n > 0 && (size_t)n + strlen(p) + 2 < sizeof absolute) {
      absolute[n] = '/'; strcpy(absolute + n + 1, p); target = absolute;
    }
  }
  int e = fault(target, flags & AT_REMOVEDIR ? "rmdir" : "unlink");
  if (e) { errno = e; return -1; }
  int (*real)(int, const char *, int) = dlsym(RTLD_NEXT, "unlinkat"); return real(dirfd, p, flags);
}
