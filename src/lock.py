import os
import sys
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class RunLock:
    """
    Prevent concurrent executions using a file lock with PID.
    """
    def __init__(self, lock_dir: str):
        self.lock_file = os.path.join(lock_dir, ".run.lock")
        
    @contextmanager
    def acquire(self):
        """Try to acquire the lock. Raises RuntimeError if locked."""
        if os.path.exists(self.lock_file):
            # Check if valid
            try:
                with open(self.lock_file, "r") as f:
                    content = f.read().strip()
                
                if content:
                    pid = int(content)
                    if self.is_process_running(pid):
                        raise RuntimeError(f"Lock file exists. Process {pid} is running.")
                    else:
                        logger.warning(f"Found stale lock file from PID {pid}. Overwriting.")
            except ValueError:
                logger.warning("Invalid lock file content. Overwriting.")
            except IOError:
                pass # Can't read, maybe race?
                
        # Write Lock
        try:
            with open(self.lock_file, "w") as f:
                f.write(str(os.getpid()))
            logger.info(f"Acquired lock: {self.lock_file} (PID {os.getpid()})")
        except IOError as e:
            raise RuntimeError(f"Failed to write lock file: {e}")
            
        try:
            yield
        finally:
            # Release Lock
            if os.path.exists(self.lock_file):
                try:
                    os.remove(self.lock_file)
                    logger.info("Released lock.")
                except OSError as e:
                    logger.error(f"Failed to remove lock file: {e}")
                    
    @staticmethod
    def is_process_running(pid: int) -> bool:
        """Check if PID is running (Cross-platform basic check)."""
        if os.name == 'nt':
            # Windows
            try:
                # Use tasklist to check PID presence
                import subprocess
                cmd = f"tasklist /FI \"PID eq {pid}\""
                output = subprocess.check_output(cmd, shell=True).decode()
                return str(pid) in output
            except:
                return False # Assume not running if check fails
        else:
            # POSIX
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
