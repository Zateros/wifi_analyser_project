from PySide6.QtCore import QObject, Signal, Slot, QThread
from utils.util import getResourcePath
from utils.literals import SOCKET_PATH

import subprocess, socket, time, json


class Worker(QObject):
    def __init__(self):
        super().__init__()
        self.process = None
        self.sock = None
        self.signals = WorkerSignals()

        self.comm_thread = QThread()
        self.moveToThread(self.comm_thread)

        self.comm_thread.started.connect(self._run_connection_loop)

        self.start_worker_server()
        self.comm_thread.start()

    @Slot()
    def start_worker_server(self):
        try:
            self.process = subprocess.Popen(
                [
                    "pkexec",
                    "/usr/bin/env",
                    "python3",
                    getResourcePath("analyser_server.py"),
                ]
            )
            print(self.process)
            return True
        except Exception as e:
            print(f"Failed to start worker: {e}")
            self.signals.connection_error.emit(f"Failed to start worker: {e}")
            return False

    @Slot()
    def _run_connection_loop(self):
        retries = 10
        for i in range(retries):
            if self.process is None or self.process.poll() is not None:
                self.signals.connection_error.emit(
                    "Worker process terminated prematurely."
                )
                return

            try:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(SOCKET_PATH)
                print("Successfully connected to worker socket.")
                self.signals.connected.emit()
                break
            except (ConnectionRefusedError, FileNotFoundError):
                print(f"Waiting for worker socket... (attempt {i+1})")
                time.sleep(5)
        else:
            print("Error: Could not connect to worker socket.")
            self.signals.connection_error.emit(
                "Connection failed: Max retries reached."
            )
            return

        try:
            while True:
                data = self.sock.recv(1024)
                if not data:
                    print("Worker disconnected")
                    break

                response = data.decode("utf-8")
                if response == "MEASUREMENT_FINISHED":
                    self.signals.finished.emit()
                elif response.startswith("COMMAND_ERROR"):
                    error_json = json.loads(response.removeprefix("COMMAND_ERROR "))
                    self.signals.command_error.emit(error_json)
                else:
                    self.signals.response_received.emit(response)

        except ConnectionResetError:
            print("Connection reset by worker.")
        except Exception as e:
            print(f"Error in listening loop: {e}")
        finally:
            self.sock.close()
            self.sock = None
            self.signals.disconnected.emit()
            print("Socket listener thread finished.")

    @Slot(str)
    def send_command(self, command):
        if self.sock:
            try:
                self.sock.sendall(command.encode("utf-8"))
            except Exception as e:
                print(f"Error sending command: {e}")
                self.sock.close()
                self.sock = None
        else:
            print("Error: Not connected, cannot send command.")

    @Slot()
    def stop(self):
        if self.sock:
            self.send_command("EXIT")

        self.comm_thread.quit()
        self.comm_thread.wait()

        if self.process:
            self.process.wait()
        print("Worker stopped.")


class WorkerSignals(QObject):
    connected = Signal()
    disconnected = Signal()
    finished = Signal()
    command_error = Signal(dict)
    response_received = Signal(str)
    connection_error = Signal(str)
