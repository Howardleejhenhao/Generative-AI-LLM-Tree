import json
import os
import selectors
import subprocess
from typing import Any, Dict, List, Optional

from .schema import ToolDefinition, ToolResult
from .client import BaseMCPClient


class StdioMCPClient(BaseMCPClient):
    """
    Client for MCP servers running as local subprocesses via stdio.
    Implements a real handshake and JSON-RPC communication.
    """

    def __init__(self, config: Dict[str, Any]):
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._is_initialized = False
        self._server_info = {}
        self._capabilities = {}

        self.config = config
        self.server_label = config.get("label", "Local Stdio Server")
        self.transport_kind = "stdio"

        # Stdio-specific config parsing
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
        self.cwd = config.get("cwd", None)
        self.timeout = self._normalize_timeout(config.get("timeout", 30))

    @staticmethod
    def _normalize_timeout(value: Any) -> float:
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            return 30.0
        return timeout if timeout > 0 else 30.0

    def _start_process(self):
        if self._process is not None and self._process.poll() is None:
            return

        if not self.command:
            raise ValueError("No command configured for stdio transport.")

        env = os.environ.copy()
        if self.env:
            env.update(self.env)

        try:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=self.cwd,
                text=True,
                bufsize=1  # Line buffered
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start subprocess: {str(e)}")

    def _stop_process(self):
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            self._is_initialized = False

    def _send_json(self, data: dict):
        if not self._process or self._process.stdin is None:
            raise RuntimeError("Subprocess not running or stdin unavailable.")
        
        json_line = json.dumps(data)
        try:
            self._process.stdin.write(json_line + "\n")
            self._process.stdin.flush()
        except BrokenPipeError:
            self._stop_process()
            raise RuntimeError("Subprocess stdin broken pipe.")

    def _read_json(self, timeout: Optional[float] = None) -> dict:
        if not self._process or self._process.stdout is None:
            raise RuntimeError("Subprocess not running or stdout unavailable.")

        selector = selectors.DefaultSelector()
        try:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            ready = selector.select(timeout if timeout is not None else self.timeout)
        finally:
            selector.close()

        if not ready:
            self._stop_process()
            raise RuntimeError(
                f"Timed out waiting for stdio MCP response after {timeout if timeout is not None else self.timeout} seconds."
            )

        line = self._process.stdout.readline()
        if not line:
            # Check stderr for potential error messages
            stderr_out = ""
            if self._process.stderr:
                try:
                    # Non-blocking read would be better, but let's try a quick check
                    stderr_out = self._process.stderr.read()
                except:
                    pass
            self._stop_process()
            raise RuntimeError(f"Subprocess stdout closed unexpectedly. {stderr_out}")
        
        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse JSON from subprocess: {line}. Error: {str(e)}")

    def _request(self, method: str, params: dict) -> dict:
        self._start_process()
        self._request_id += 1
        req_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        
        self._send_json(request)
        
        # Simple implementation: expect response immediately
        # In a real MCP environment, we might receive notifications first.
        # But for v1 handshake, we assume sequential responses for our requests.
        while True:
            response = self._read_json(timeout=self.timeout)
            if response.get("id") == req_id:
                if "error" in response:
                    err = response["error"]
                    raise RuntimeError(f"MCP Error {err.get('code')}: {err.get('message')}")
                if "result" not in response:
                    raise RuntimeError(f"Invalid JSON-RPC response: missing 'result' or 'error' in {response}")
                return response.get("result", {})
            # If it's a notification, we might want to handle it or just skip for now
            if "id" not in response:
                continue
            # If it's a different ID, something is wrong in our simple sync flow
            raise RuntimeError(f"Received response with unexpected ID: {response.get('id')}. Expected: {req_id}")

    def _notify(self, method: str, params: dict = None):
        self._start_process()
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params is not None:
            notification["params"] = params
        
        self._send_json(notification)

    def _ensure_initialized(self):
        if self._is_initialized:
            # Check if process is still alive
            if self._process and self._process.poll() is None:
                return
            else:
                self._is_initialized = False

        try:
            result = self._request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "LLM-Tree", "version": "1.0.0"}
            })
            self._server_info = result.get("serverInfo", {})
            self._capabilities = result.get("capabilities", {})
            
            self._notify("notifications/initialized")
            self._is_initialized = True
        except Exception as e:
            self._stop_process()
            raise RuntimeError(f"MCP Handshake failed: {str(e)}")

    def list_tools(self) -> List[ToolDefinition]:
        self._ensure_initialized()
        try:
            result = self._request("tools/list", {})
            tools_data = result.get("tools", [])
            
            tools = []
            for t_data in tools_data:
                tools.append(ToolDefinition(
                    name=t_data.get("name"),
                    description=t_data.get("description", ""),
                    input_schema=t_data.get("inputSchema", {"type": "object", "properties": {}}),
                ))
            return tools
        except Exception as e:
            # Don't stop process here unless it's a transport error, 
            # but _request already handles transport errors.
            raise RuntimeError(f"Failed to list tools: {str(e)}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        try:
            self._ensure_initialized()
            result = self._request("tools/call", {
                "name": name,
                "arguments": arguments
            })
            
            content = result.get("content", [])
            is_error = result.get("isError", False)
            
            return ToolResult(
                content=content,
                is_error=is_error,
                metadata={
                    "transport": "stdio",
                    "server_info": self._server_info
                }
            )
        except Exception as e:
            return ToolResult.from_error(f"Stdio MCP call failed: {str(e)}")

    def get_server_info(self) -> Dict[str, Any]:
        info = {
            "label": self.server_label,
            "transport": self.transport_kind,
            "command": self.command,
        }
        if self._is_initialized:
            info["status"] = "connected"
            info["server_info"] = self._server_info
            info["capabilities"] = self._capabilities
        else:
            if self._process and self._process.poll() is None:
                info["status"] = "starting"
            else:
                info["status"] = "skeleton" if self.command else "disconnected"
        return info

    def __del__(self):
        try:
            self._stop_process()
        except Exception:
            pass
