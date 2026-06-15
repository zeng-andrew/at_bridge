"""Serial port handler for AT command communication."""

import time
from dataclasses import dataclass
from typing import Optional

import serial
import serial.tools.list_ports


@dataclass
class PortConfig:
    """Serial port configuration."""

    baudrate: int = 115200
    bytesize: int = serial.EIGHTBITS
    parity: str = serial.PARITY_NONE
    stopbits: int = serial.STOPBITS_ONE
    timeout: float = 1.0
    rtscts: bool = False
    xonxoff: bool = False


class SerialHandler:
    """Manages serial port connection and AT command communication."""

    def __init__(self):
        self._connection: Optional[serial.Serial] = None
        self._config = PortConfig()

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_open

    @property
    def current_port(self) -> Optional[str]:
        return self._connection.port if self.is_connected else None

    @staticmethod
    def list_ports() -> list[dict]:
        """List all available COM ports.

        Returns:
            List of dicts with port info: device, name, description, hwid, vid, pid.
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                "device": port.device,
                "name": port.name,
                "description": port.description,
                "hwid": port.hwid,
                "vid": f"0x{port.vid:04X}" if port.vid else None,
                "pid": f"0x{port.pid:04X}" if port.pid else None,
                "serial_number": port.serial_number,
                "manufacturer": port.manufacturer,
                "product": port.product,
            })
        return ports

    def configure(
        self,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 1.0,
        rtscts: bool = False,
        xonxoff: bool = False,
    ) -> dict:
        """Configure serial port parameters.

        Args:
            baudrate: Baud rate (e.g. 9600, 115200, 921600).
            bytesize: Data bits (5, 6, 7, 8).
            parity: Parity ('N'=None, 'E'=Even, 'O'=Odd, 'M'=Mark, 'S'=Space).
            stopbits: Stop bits (1, 1.5, 2).
            timeout: Read timeout in seconds.
            rtscts: Hardware flow control (RTS/CTS).
            xonxoff: Software flow control (XON/XOFF).

        Returns:
            Current configuration dict.
        """
        bytesize_map = {5: serial.FIVEBITS, 6: serial.SIXBITS,
                        7: serial.SEVENBITS, 8: serial.EIGHTBITS}
        parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN,
                       "O": serial.PARITY_ODD, "M": serial.PARITY_MARK,
                       "S": serial.PARITY_SPACE}
        stopbits_map = {1: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE,
                        2: serial.STOPBITS_TWO}

        self._config = PortConfig(
            baudrate=baudrate,
            bytesize=bytesize_map.get(bytesize, serial.EIGHTBITS),
            parity=parity_map.get(parity.upper(), serial.PARITY_NONE),
            stopbits=stopbits_map.get(stopbits, serial.STOPBITS_ONE),
            timeout=timeout,
            rtscts=rtscts,
            xonxoff=xonxoff,
        )

        # Apply to existing connection if open
        if self.is_connected:
            self._connection.baudrate = self._config.baudrate
            self._connection.bytesize = self._config.bytesize
            self._connection.parity = self._config.parity
            self._connection.stopbits = self._config.stopbits
            self._connection.timeout = self._config.timeout
            self._connection.rtscts = self._config.rtscts
            self._connection.xonxoff = self._config.xonxoff

        return self.get_config()

    def get_config(self) -> dict:
        """Get current serial port configuration."""
        return {
            "baudrate": self._config.baudrate,
            "bytesize": self._config.bytesize,
            "parity": self._config.parity,
            "stopbits": self._config.stopbits,
            "timeout": self._config.timeout,
            "rtscts": self._config.rtscts,
            "xonxoff": self._config.xonxoff,
        }

    def open(self, port: str) -> dict:
        """Open a COM port for communication.

        Args:
            port: The COM port device name (e.g. 'COM3' on Windows, '/dev/ttyUSB0' on Linux).

        Returns:
            Status dict with port and config info.

        Raises:
            serial.SerialException: If the port cannot be opened.
        """
        if self.is_connected:
            self.close()

        self._connection = serial.Serial(
            port=port,
            baudrate=self._config.baudrate,
            bytesize=self._config.bytesize,
            parity=self._config.parity,
            stopbits=self._config.stopbits,
            timeout=self._config.timeout,
            rtscts=self._config.rtscts,
            xonxoff=self._config.xonxoff,
        )

        return {
            "status": "connected",
            "port": port,
            "config": self.get_config(),
        }

    def close(self) -> dict:
        """Close the current COM port connection.

        Returns:
            Status dict.
        """
        if self._connection and self._connection.is_open:
            port = self._connection.port
            self._connection.close()
            self._connection = None
            return {"status": "disconnected", "port": port}
        return {"status": "not_connected"}

    def send_at_command(self, command: str, read_until: Optional[str] = None) -> dict:
        """Send an AT command and read the response.

        Args:
            command: The AT command to send (e.g. 'AT', 'AT+CGMI', 'AT+CSQ').
                     'AT' prefix will be auto-prepended if missing.
            read_until: Optional termination string to read until.
                        Default behavior reads all available data after timeout.

        Returns:
            Dict with command, raw response, and timing info.

        Raises:
            RuntimeError: If no port is connected.
        """
        if not self.is_connected:
            raise RuntimeError("No COM port is currently open. Use open_port first.")

        # Ensure AT prefix
        cmd = command.strip()
        if not cmd.upper().startswith("AT"):
            cmd = f"AT{cmd}"

        # Flush input buffer before sending
        self._connection.reset_input_buffer()

        # Send command with \r\n terminator
        start_time = time.time()
        full_cmd = f"{cmd}\r\n"
        self._connection.write(full_cmd.encode("utf-8"))

        # Read response
        response_lines = []
        while True:
            line = self._connection.readline()
            try:
                decoded = line.decode("utf-8", errors="replace").strip()
            except Exception:
                decoded = str(line)
            if not decoded:
                # Timeout reached with no data
                if not response_lines:
                    continue
                else:
                    break
            response_lines.append(decoded)
            # Stop on standard OK/ERROR responses
            if decoded in ("OK", "ERROR") or decoded.startswith("+CME ERROR"):
                break
            if read_until and read_until in decoded:
                break

        elapsed_ms = round((time.time() - start_time) * 1000, 1)

        return {
            "command": cmd,
            "response": response_lines,
            "raw": "\r\n".join(response_lines),
            "elapsed_ms": elapsed_ms,
        }

    def auto_detect(
        self,
        baudrates: Optional[list[int]] = None,
        probe_timeout: float = 0.5,
        test_command: str = "AT",
    ) -> list[dict]:
        """Auto-detect AT-capable devices by probing all available COM ports.

        For each port, tries the configured baud rates (or a common set),
        sends the test command, and checks for an 'OK' response.

        If a port is already open, it is saved before probing and restored after.

        Args:
            baudrates: Baud rates to try. Default: [115200, 9600, 921600, 460800, 230400, 57600, 38400, 19200].
            probe_timeout: Read timeout per attempt in seconds. Shorter = faster scan.
            test_command: AT command to send for probing. Default: 'AT'.

        Returns:
            List of dicts, one per discovered device, with port info, working
            baudrate, response, and probe stats.
        """
        if baudrates is None:
            baudrates = [115200, 9600, 921600, 460800, 230400, 57600, 38400, 19200]

        # Save current connection state
        saved_port = None
        if self.is_connected:
            saved_port = self._connection.port
            saved_config = {
                "baudrate": self._config.baudrate,
                "bytesize": self._config.bytesize,
                "parity": self._config.parity,
                "stopbits": self._config.stopbits,
                "timeout": self._config.timeout,
                "rtscts": self._config.rtscts,
                "xonxoff": self._config.xonxoff,
            }
            self.close()

        ports = self.list_ports()
        discovered = []

        for port_info in ports:
            device = port_info["device"]
            port_result = {
                "device": device,
                "description": port_info["description"],
                "manufacturer": port_info.get("manufacturer"),
                "vid": port_info.get("vid"),
                "pid": port_info.get("pid"),
                "serial_number": port_info.get("serial_number"),
                "working_baudrate": None,
                "response": None,
                "tried_baudrates": [],
                "error": None,
            }

            for rate in baudrates:
                port_result["tried_baudrates"].append(rate)
                try:
                    conn = serial.Serial(
                        port=device,
                        baudrate=rate,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=probe_timeout,
                        rtscts=False,
                        xonxoff=False,
                    )

                    # Flush, send, and read
                    conn.reset_input_buffer()
                    conn.write(f"{test_command}\r\n".encode("utf-8"))

                    response_lines = []
                    deadline = time.time() + probe_timeout
                    while time.time() < deadline:
                        line = conn.readline()
                        try:
                            decoded = line.decode("utf-8", errors="replace").strip()
                        except Exception:
                            decoded = str(line)
                        if decoded:
                            response_lines.append(decoded)
                            if decoded == "OK" or decoded == "ERROR":
                                break

                    conn.close()

                    # Check if we got a valid AT response (contains "OK")
                    response_text = "\r\n".join(response_lines)
                    if "OK" in response_lines:
                        port_result["working_baudrate"] = rate
                        port_result["response"] = response_text
                        break  # Found working baudrate, stop trying this port

                except serial.SerialException:
                    # Port in use or can't be opened — skip this baudrate attempt
                    continue

            if port_result["working_baudrate"] is not None:
                discovered.append(port_result)

        # Restore previous connection
        if saved_port:
            self.configure(**saved_config)
            try:
                self.open(saved_port)
            except serial.SerialException:
                pass  # Port may no longer be available, that's ok

        return discovered

    def batch_test(
        self,
        commands: list[str],
        timeout: float = 1.0,
    ) -> list[dict]:
        """Batch-test a list of AT commands on the currently connected port.

        Args:
            commands: List of AT command strings to test.
            timeout: Per-command read timeout.

        Returns:
            List of result dicts with keys:
              cmd, status (PASS|OK|CME|ERR|EXCEPTION),
              has_ok, has_error, has_cme,
              data (non-status response lines),
              raw, elapsed_ms.
        """
        if not self.is_connected:
            raise RuntimeError("No COM port open. Use at_open_port first.")

        results = []
        orig_timeout = self._config.timeout
        self._config.timeout = timeout
        if self._connection:
            self._connection.timeout = timeout

        for cmd in commands:
            cmd_stripped = cmd.strip()
            t0 = time.time()
            try:
                r = self.send_at_command(cmd_stripped)
                raw = r["raw"]
                elapsed = r["elapsed_ms"]
            except Exception as e:
                raw = str(e)
                elapsed = round((time.time() - t0) * 1000, 1)

            # Parse
            lines = [l.strip() for l in raw.replace("\r\n", "\n").split("\n") if l.strip()]
            has_ok = "OK" in lines
            has_error = any("ERROR" in l for l in lines) and not has_ok
            has_cme = any("CME ERROR" in l for l in lines)
            data_lines = [l for l in lines if l != "OK" and "ERROR" not in l and "CME ERROR" not in l]

            if has_cme:
                status = "CME"
            elif has_error:
                status = "ERR"
            elif data_lines:
                status = "PASS"
            elif has_ok:
                status = "OK"
            else:
                status = "UNKNOWN"

            results.append({
                "cmd": cmd_stripped,
                "status": status,
                "has_ok": has_ok,
                "has_error": has_error,
                "has_cme": has_cme,
                "data": data_lines[:10],
                "raw": raw[:500],
                "elapsed_ms": elapsed,
            })

        # Restore original timeout
        self._config.timeout = orig_timeout
        if self._connection:
            self._connection.timeout = orig_timeout

        return results
