"""
Cross-platform advisory file locking.

서버(Linux)는 fcntl.flock 을 쓰지만 Windows 에는 fcntl 이 없다.
호출부 코드를 그대로 두기 위해 fcntl 과 동일한 이름(flock / LOCK_EX /
LOCK_SH / LOCK_UN)을 노출하는 얇은 shim 을 제공한다.

사용법 (fcntl 을 그대로 대체):
    from utils.file_lock import flock, LOCK_EX, LOCK_SH, LOCK_UN
    flock(f.fileno(), LOCK_EX)
"""
import os

LOCK_SH = 1  # shared
LOCK_EX = 2  # exclusive
LOCK_NB = 4  # non-blocking
LOCK_UN = 8  # unlock

if os.name == "nt":
    import msvcrt

    # msvcrt 는 바이트 범위 잠금만 지원한다. 파일 선두 1바이트를 토큰으로
    # 사용하면 EOF 를 넘어서도 잠글 수 있어 빈 파일에도 안전하다.
    _LOCK_BYTES = 1

    def flock(fd, operation):
        """fcntl.flock 과 호환되는 Windows 구현.

        msvcrt 에는 공유(읽기) 잠금이 없으므로 LOCK_SH 도 배타 잠금으로
        처리한다. 잠금 범위는 파일 선두 1바이트이며 파일 내용에는 영향이 없다.
        """
        # 잠금은 현재 파일 위치를 기준으로 걸리므로 선두로 되돌린 뒤 복원한다.
        saved_pos = os.lseek(fd, 0, os.SEEK_CUR)
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if operation & LOCK_UN:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, _LOCK_BYTES)
            else:
                mode = msvcrt.LK_NBLCK if operation & LOCK_NB else msvcrt.LK_LOCK
                msvcrt.locking(fd, mode, _LOCK_BYTES)
        except OSError:
            # 이미 잠겨 있거나(동일 프로세스 재진입) 잠금을 지원하지 않는
            # 파일 시스템인 경우. 로컬 단일 프로세스 실행에서는 치명적이지
            # 않으므로 조용히 넘어간다.
            pass
        finally:
            os.lseek(fd, saved_pos, os.SEEK_SET)

else:
    import fcntl as _fcntl

    LOCK_SH = _fcntl.LOCK_SH
    LOCK_EX = _fcntl.LOCK_EX
    LOCK_NB = _fcntl.LOCK_NB
    LOCK_UN = _fcntl.LOCK_UN
    flock = _fcntl.flock
