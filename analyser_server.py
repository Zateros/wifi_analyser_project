from argparse import Namespace
from utils.analyser_utils import measure
from utils.literals import SOCKET_PATH, MEASURE_HEADERS
import csv, os, sys, socket, json, pwd

CMD_START = "START_MEASUREMENT"
CMD_CHANGE = "CHANGE"
CMD_EXIT = "EXIT"

RES_EMPTY_ARGS = b"EMPTY_ARGS"
RES_MEASUREMENT_FINISHED = b"MEASUREMENT_FINISHED"
RES_CHANGE_OK = b"CHANGE_OK"
RES_ACK_EXIT = b"ACK_EXIT"
RES_UNKNOWN_COMMAND = b"UNKNOWN_COMMAND"
RES_COMMAND_ERROR_PREFIX = "COMMAND_ERROR "


# https://stackoverflow.com/questions/564695/is-there-a-way-to-change-effective-process-name-in-python
def setProcName(newname):
    from ctypes import cdll, byref, create_string_buffer

    libc = cdll.LoadLibrary("libc.so.6")
    buff = create_string_buffer(len(newname) + 1)
    buff.value = newname.encode()
    libc.prctl(15, byref(buff), 0, 0, 0)


def log(msg, file=sys.stdout):
    print(f"[Worker]: {msg}", file=file)


def createCsvfile(args, original_uid, original_gid):
    first_write = not os.path.exists(args.out)
    csvfile = open(args.out, "a", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=MEASURE_HEADERS)
    if first_write:
        os.chown(args.out, original_uid, original_gid)
        writer.writeheader()
        csvfile.flush()

    return (writer, csvfile)


def createErrorResponse(command, error):
    return (
        RES_COMMAND_ERROR_PREFIX + json.dumps({"command": command, "error": str(error)})
    ).encode()


def getOriginalUserIDs():
    try:
        uid = int(os.environ["PKEXEC_UID"] or os.environ["SUDO_UID"])
        gid = pwd.getpwuid(uid).pw_gid
        log(f"Original UID is {uid} and GID is {gid}")
        return uid, gid
    except (KeyError, ValueError, TypeError):
        log(
            "ERROR: Could not get PKEXEC_UID/SUDO_UID. Run via pkexec or sudo.",
            file=sys.stderr,
        )
        sys.exit(1)


def handleStart(command_args, args, writer, csvfile):
    if not writer or not csvfile:
        log("Measurements arguments not set before measurement start!")
        return RES_EMPTY_ARGS

    try:
        pos_x, pos_y, pos_room = command_args.split(",")
    except ValueError as e:
        log(f"Invalid position arguments: {command_args}")
        return createErrorResponse(CMD_START, e)

    row = {h: "" for h in MEASURE_HEADERS}
    row.update(
        {
            "position_x": pos_x,
            "position_y": pos_y,
            "position_in_room": pos_room,
        }
    )

    measure(args, row, writer, csvfile)
    return RES_MEASUREMENT_FINISHED


def handleChange(command_args, args, uid, gid, csvfile):
    options = json.loads(command_args)

    args.iperf_addr = options["iperf_addr"]
    args.iperf_port = options["iperf_port"]
    args.iface = options["iface"]
    args.target = options["target"]
    args.out = os.path.join(options["pwd"], options["out"])

    if csvfile:
        csvfile.close()

    writer, csvfile = createCsvfile(args, uid, gid)
    return RES_CHANGE_OK, writer, csvfile


def handleExit():
    log("Shutting down...")
    return RES_ACK_EXIT, True


def handleClient(conn, args, uid, gid, writer, csvfile):
    last_command = ""
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break

            request = data.decode("utf-8").strip()
            log(f"Received '{request}'")

            if not request:
                continue

            parts = request.split(" ", maxsplit=1)
            command, command_args = parts[0], (parts[1] if len(parts) > 1 else "")
            last_command = command

            response = b""
            should_exit = False

            if command == CMD_START:
                response = handleStart(command_args, args, writer, csvfile)
            elif command == CMD_CHANGE:
                response, writer, csvfile = handleChange(
                    command_args, args, uid, gid, csvfile
                )
            elif command == CMD_EXIT:
                response, should_exit = handleExit()
            else:
                conn.sendall(RES_UNKNOWN_COMMAND)

            conn.sendall(response)

            if should_exit:
                return writer, csvfile, True

        except Exception as e:
            log(f"Error while handling client: {e}")
            conn.sendall(createErrorResponse(last_command, e))

    return writer, csvfile, False


def runSocket():
    uid, gid = getOriginalUserIDs()

    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    args = Namespace(iperf_addr="", iperf_port="", target="", out="", iface="")
    writer, csvfile = None, None

    try:
        server.bind(SOCKET_PATH)
        os.chown(SOCKET_PATH, uid, -1)
        os.chmod(SOCKET_PATH, 0o600)

        log(f"Socket server listening at {SOCKET_PATH}")
        server.listen(1)

        while True:
            log("Waiting for connection...")
            conn, _ = server.accept()
            log("Client connected.")

            writer, csvfile, should_exit = handleClient(
                conn, args, uid, gid, writer, csvfile
            )
            if should_exit:
                break

    except Exception as e:
        log(f"Server error: {e}", file=sys.stderr)
    finally:
        server.close()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        if csvfile:
            csvfile.close()
        log("Server shut down")


if __name__ == "__main__":
    if os.getuid() == 0:
        setProcName("Analyser Worker")
        runSocket()
    else:
        print("Root priviledges required to run!", file=sys.stderr)
        exit(1)
