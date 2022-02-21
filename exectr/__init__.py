import os
import pickle
import pexpect
import time
from datetime import datetime
from enum import Enum
from pygments import highlight
from pygments.lexers import BashLexer
from pygments.formatters import TerminalFormatter

DEBUG = False

__version__ = '0.0.4'

# distributed:
# if distributed
# place lock on state file when writing/loading?
# load state before every exec
# write running before every exec
#    write only current line
#    do this for skipped too!
# if dependency is running? wait then load again then recheck
#   after wait, dependency may be succeeded
#   but currebt line may also be succeeded / not
#   if yes, continue
# write state after every exec
#    reload, change only the current running to done
#    usually we don't store running, here we should
#    change running storage
#    handle running in loaded state - if distrib
# (maybe) worker info in state? per line start time?
# separate log per worker (in write state and pexpect logfile)
# merged log at the end, prepend each line with worker id and time?
#   X won't work, time is not per-output-line

# add reason for skip to state?

def print_version():
    print("""
  ┌───────┐ ┌─┐  ┌─┐ ┌───────┐ ┌─────┐ ┌─┐ ┌─┐ ┌──────┐ ┌───┐ ┌─┬───┐
  └───────┘ │ │  │ │ └───────┘ ├─────┘ │ │ │ │ └──────┘ │   │ │ │   │
            └─┤  ├─┘           │       │ │ │ │          │   │ │ ├─┬─┘
  ┌────┐      ├──┤   ┌────┐    │       │ │ │ │   ┌──┐   │   │ │ │ │
  └────┘      ├──┤   └────┘    │       └─┘ └─┘   │  │   │   │ │ │ ├─┐
            ┌─┤  ├─┐           │                 │  │   │   │ │ │ │ │
  ┌───────┐ │ │  │ │ ┌───────┐ ├─────┐ ┌─────┐   │  │   │   │ │ │ │ │
  └───────┘ └─┘  └─┘ └───────┘ └─────┘ └─────┘   └──┘   └───┘ └─┘ └─┘
  """)
    print("Executor version {}".format(__version__))
class St(Enum):
    UNTREATED = 0
    SKIPPED = 1
    EXECUTING = 2
    SUCCEEDED = 3
    FAILED = 4

def as_symbol(st):
    if st == St.UNTREATED:
        return "  "
    elif st == St.SKIPPED:
        return "- "
    elif st == St.EXECUTING:
        return "->"
    elif st == St.SUCCEEDED:
        return "✓ "
    elif st == St.FAILED:
        return "✗ "
    else:
        raise ValueError

class Line(object):
    idx = None
    command = None
    origtext = None
    status = St.UNTREATED
    dependencies = None
    retcode = None
    output = None
    dbginfo = None
    tag = None
    always = "no"

    def __init__(self, idx, command, origtext):
        self.idx = idx
        self.command = command
        self.origtext = origtext
        self.dependencies = []

    def __repr__(self):
        return '<Line {} {} {} {} {} {} {} {} {}>'.format(
            self.idx, self.status, self.tag, self.dependencies, self.always,
            self.command, self.retcode, self.output, self.dbginfo)

    def human(self):
        hl_text = highlight(self.origtext, BashLexer(), TerminalFormatter())
        symbol = as_symbol(self.status)
        idx = self.idx
        if self.command is None:
            idx = "   "
            symbol = " "
        return '{} {:>3} {}'.format(symbol, idx, hl_text)

def pretty_print(state):
    print("")
    human_lines = "\n".join([line.origtext for line in state])
    hl_human_lines = highlight(human_lines, BashLexer(), TerminalFormatter())
    for hl_linetext, line in zip(hl_human_lines.split("\n"), state):
        symbol = as_symbol(line.status)
        idx = line.idx
        if line.command is None:
            idx = "   "
            symbol = "  "
        print('{} {:>3} {}'.format(symbol, idx, hl_linetext))

def all_succeeded(state):
    for line in state:
        if line.status != St.SUCCEEDED:
            return False
    return True

def split_lines(filetext):
    lines = filetext.split('\n')
    # we want to keep the original numbering so we cant just ignore '\\\n'
    for i in range(len(lines))[::-1]:
        line = lines[i]
        if line.endswith('\\'):
            nextline = ""
            if i + 1 < len(lines):
                nextline = lines[i + 1] + ""
                lines[i + 1] = None
            line = line[:-2] + nextline
            lines[i] = line
    return filetext.split('\n'), lines

def is_comment(linetext):
    if linetext is None:
        return False
    return linetext.strip(" ").startswith('#')

def find_line_with_tag(tag, state, before=None):
    for line in state:
        if before is not None and line.idx == before:
            break
        if line.tag == tag:
            return line
    return None

def find_line_with_idx(idx, state):
    for line in state:
        if line.idx == idx:
            return line
    return None

def up_to(state, idx):
    lines = []
    for line in state:
        if line.idx == idx:
            break
        lines.append(line)
    return lines

def after(state, idx):
    lines = []
    passed = False
    for line in state:
        if line.idx == idx:
            passed = True
            continue
        if passed:
            lines.append(line)
    return lines

def assign_dependencies(state):
    for line in state:
        if not is_comment(line.command):
            continue
        line.dbginfo = "Comment"
        idx = line.idx
        nextline = find_line_with_idx(idx + 1, state)
        args = line.command.strip(" #").split(" ")
        if args and args.pop(0) == "executor":
            if args:
                directive = args.pop(0)
            else:
                raise ValueError("executor directive not specified: {}".format(line.command))
                continue
            if nextline is None:
                print("Warning: executor directive specified as last line. Ignoring.")
                break
            if directive == "set-dependent":
                # all following lines depend on their predecessor
                for lnpredecessor, ln in zip(after(state, idx), after(state, idx+1)):
                    ln.dependencies.append(lnpredecessor.idx)
            elif directive == "set-independent":
                # all following lines lose their dependency
                for ln in after(state, idx):
                    ln.dependencies = []
            elif directive == "always":
                nextline.always = "always"
            elif directive == "always-try":
                nextline.always = "always-try"
            elif directive == "if":
                if args:
                    tag = args.pop(0)
                    try:
                        condition = int(tag)
                    except ValueError:
                        target = find_line_with_tag(tag, state, before=idx)
                        if target is None:
                            raise ValueError("if directive: tag not found: {}".format(line.command))
                        condition = target.idx
                else:
                    raise ValueError("if condition not specified (# executor if NUMBER/TAG): {}".format(
                        line.command))
                    continue
                nextline.dependencies.append(condition)
            elif directive == "tag":
                if args:
                    tag = args.pop(0)
                    if find_line_with_tag(tag, state, before=idx) is not None:
                        raise ValueError("tag directive: tag already exists: {}".format(line.command))
                    nextline.tag = tag
                else:
                    raise ValueError("tag not specified (# executor tag TAG): {}".format(line.command))
                    continue

            else:
                raise ValueError("unknown directive: {} in {}".format(directive, line.command))
        else:
            continue

def detect_incompatible_commands(state):
    for line in state:
        if line.command is None:
            continue
        if line.command.strip(" ").startswith("set -e"):
            raise ValueError("line {} in script: \n{} \n set -e command is not supported".format(
                line.idx, line.command))
        if line.command.strip(" ").startswith("set -x"):
            raise ValueError("line {} in script: \n{} \n set -x command is not supported".format(
                line.idx, line.command))


def execute_line(line, ishell):
    if line.command is None:
        return 0, ""
    if is_comment(line.command):
        return 0, ""
    ishell.sendline(line.command)
    ishell.expect(r'\$ ', timeout=None)
    out = ishell.before.decode()
    # get retcode
    ishell.sendline("echo $?")
    ishell.expect(r'\$ ')
    ret = ishell.before.decode()
    ret = ret.split('\r\n')[1]
    ret = int(ret)
#     if DEBUG:
#         pass
#         print(out)
#         time.sleep(1)
#         if line.idx == 7:
#             return 1, ""
    return ret, out

def initialize_state(path):
    original_script = open(path, 'r').read()
    original_lines, corrected_lines = split_lines(original_script)
    state = [Line(idx+1, line, origline)
             for idx, (origline, line) in enumerate(zip(original_lines, corrected_lines))]
    assign_dependencies(state)
    detect_incompatible_commands(state)
    return state

def make_dir_if_not_exists(dir_):
    try:  # noqa
        os.makedirs(dir_)
    except OSError:
        if not os.path.isdir(dir_):
            raise

def write_state(path, state, silent=False):
    for line in state:
        if line.status == St.EXECUTING:
            line.status = St.UNTREATED
    wpath = path + ".executor"
    make_dir_if_not_exists(os.path.dirname(wpath))
    if os.path.exists(wpath):
        if not silent:
            print("Overwriting {}".format(wpath))
    else:
        if not silent:
            print("Writing {}".format(wpath))
    pickle.dump(state, open(wpath, 'wb'))

    # write log
    log = "\n".join([line.output for line in state if line.output is not None])
    log = log + "\n" + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lpath = path + ".executor.log"
    make_dir_if_not_exists(os.path.dirname(lpath))
    if os.path.exists(lpath):
        if not silent:
            print("Overwriting {}".format(lpath))
    else:
        if not silent:
            print("Writing {}".format(lpath))
    open(lpath, 'w').write(log)

def load_previous_if_exists(path, force_rerun=False, force_continue=False):
    new_state = initialize_state(path)
    prev_path = path + ".executor"
    if not os.path.exists(prev_path):
        if force_continue:
            print("Warning: no previous execution file found, but --continue flag was specified.")
            print("Proceeding anyways in 3 seconds. (Ctrl-c to cancel)")
            for i in range(3, 0, -1):
                print("{}.".format(i))
                time.sleep(1)
        return new_state
    prev_state = pickle.load(open(prev_path, 'rb'))
    if states_have_same_original_files(new_state, prev_state):
        print("Previous execution found for script (script is unchanged).")
        if all_succeeded(prev_state):
            print("Previous execution was completed successfully.")
        choice = None
        if force_rerun:
            print("Forcing rerun.")
            choice = 'f'
        if force_continue:
            choice = 'c'
        if choice is None:
            if not all_succeeded(prev_state):
                print("c Continue")
            print("f Re-run failed")
            print("a Re-run all")
            print("d Display state")
            print("q Abort")
            choice = input(">> ")
        if choice == 'c' and not all_succeeded(prev_state):
            print("Resuming from previous execution.")
            return prev_state
        if choice == 'c' and all_succeeded(prev_state):
            print("Requested to continue, but previous execution completed succesfully. Aborting.")
        elif choice == 'f':
            for line in prev_state:
                if line.status in [St.FAILED, St.SKIPPED]:
                    line.status = St.UNTREATED
            print("Re-running failed then resuming")
            return prev_state
        elif choice == 'q':
            print("Aborting.")
        elif choice == 'a':
            print("Re-running all.")
            return new_state
        elif choice == 'd':
            pretty_print(prev_state)
            return load_previous_if_exists(path)
        else:
            print("Unknown choice {}".format(choice))
        return None
    else:
        print("Previous state found for script, but script has changed.")
        if force_rerun:
            print("Forcing rerun.")
            return new_state
        yn = input("Execute new script? [y/n]")
        if yn.lower() in ['y', 'yes']:
            return new_state
        else:
            exit

def states_have_same_original_files(state1, state2):
    if len(state1) != len(state2):
        return False
    for line1, line2 in zip(state1, state2):
        if line1.origtext != line2.origtext:
            return False
    return True

def main(path="", args="", force_rerun=False, cont=False, interactive=False, debug=False, version=False):
    if path == "":
        print_version()
        print("")
        print("No path provided. Nothing to EXECUTE. Done.")
        print("(executor --help for usage.)")
        return
    if version:
        print_version()
        return
    if DEBUG:
        from IPython import get_ipython

        def enable_auto_debug():
            ipython = get_ipython()
            if ipython is None:
                print("WARNING: Auto debugging can not be enabled, please run this script with ipython")
                return
            else:
                ipython.magic("pdb 1")
        enable_auto_debug()
    path = os.path.abspath(path)
    print("Going to EXECUTE script {} {}".format(path, args))
    state = load_previous_if_exists(path, force_rerun=force_rerun, force_continue=cont)
    if state is None:
        return
    if debug:
        for line in state:
            print(line)
        input("Press enter to continue")
    # execute(state)
    ishell = pexpect.spawn("/bin/bash")
    ishell.logfile = open('/tmp/executor_running_log.txt', 'wb')
    ishell.expect(r'\$')
    if args != "":
        ishell.sendline("set {}".format(args))
        ishell.expect(r'\$')
    start_t = datetime.now()
    for line in state:
        if line.always == "no":
            # skip lines if required (dependencies, or already done)
            if line.status != St.UNTREATED:
                continue
            skip = False
            for dep in line.dependencies:
                if find_line_with_idx(dep, state).status != St.SUCCEEDED:
                    skip = True
            if skip:
                line.status = St.SKIPPED
                continue
        write_state(path, state, silent=True)
        line.status = St.EXECUTING
        print("EXECUTING ({})".format(datetime.now() - start_t))
        print("---------")
        pretty_print(state)
        execute_this_line = True
        if interactive:
            print("")
            print("Going to execute line {}. Execute or skip? [e/s]".format(line.idx))
            choice = input(">> ")
            if choice.lower() in ["e", "execute"]:
                execute_this_line = True
            else:
                execute_this_line = False
        if execute_this_line:
            retcode, output = execute_line(line, ishell)
            line.retcode = retcode
            line.output = output
            if retcode == 0:
                line.status = St.SUCCEEDED
            else:
                line.status = St.FAILED
        else:
            line.status = St.SKIPPED
        if line.status != St.SUCCEEDED and line.always == "always":
            print("Always-required command failed. Aborting.")
            break
    print("EXECUTING ({})".format(datetime.now() - start_t))
    print("---------")
    pretty_print(state)
    print("")
    print("DONE.")
    print("")
    write_state(path, state)
    if DEBUG:
        globals().update(locals())
    ishell.logfile.close()
    ishell.close()