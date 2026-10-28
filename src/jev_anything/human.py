"""Human-only original-desktop handoff. Never reads pixels or sends GUI input."""
import sys
try:
    import termios
except ImportError:
    termios = None
from urllib.parse import urlsplit


def terminal_handler(view_url=None, *, access_file=None, stream=None, output=None):
    if view_url:
        uri = urlsplit(view_url)
        if uri.scheme not in ('http', 'https') or not uri.hostname or uri.username or uri.password:
            raise ValueError('Human viewer must be an explicit HTTP(S) endpoint without embedded credentials')
    stream = stream if stream is not None else sys.stdin
    output = output if output is not None else sys.stderr

    def handoff(request):
        output.write('\n自动操作已暂停。请在同一原 GUI 中操作：\n' + request['instructions'] + '\n')
        if view_url: output.write('用户桌面入口：' + view_url + '\n')
        if access_file: output.write('用户桌面入口保存在私有文件：' + str(access_file) + '\n')
        output.write('完成后输入 RESUME，取消输入 CANCEL；恢复后仍须通过新的公开状态检查。\n')
        output.flush()
        terminal = None
        try:
            if termios is not None and hasattr(stream,'isatty') and stream.isatty():
                terminal = termios.tcgetattr(stream.fileno())
                quiet = list(terminal);quiet[3] &= ~termios.ECHO
                termios.tcsetattr(stream.fileno(),termios.TCSANOW,quiet)
            while True:
                line = stream.readline()
                if not line: return 'cancel'
                if line.strip() == 'RESUME': return 'resume'
                if line.strip() == 'CANCEL': return 'cancel'
                output.write('请输入 RESUME 或 CANCEL；不记录其他输入。\n'); output.flush()
        except KeyboardInterrupt:
            return 'cancel'
        finally:
            if terminal is not None:termios.tcsetattr(stream.fileno(),termios.TCSANOW,terminal)
    return handoff
