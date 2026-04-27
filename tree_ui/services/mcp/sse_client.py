import json
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .client import BaseMCPClient
from .schema import ToolDefinition, ToolResult


class SSEMCPClient(BaseMCPClient):
    """
    MCP client that uses the SSE transport.
    It opens a long-lived SSE stream, waits for the server to announce the
    message endpoint, then sends JSON-RPC requests over HTTP POST.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_label = config.get("label", "Remote SSE Server")
        self.transport_kind = "sse"
        self.endpoint = config.get("endpoint", "")
        self.timeout = self._normalize_timeout(config.get("timeout", 30))
        self.headers = self._normalize_headers(config.get("headers", {}))

        self._request_id = 0
        self._is_initialized = False
        self._server_info: Dict[str, Any] = {}
        self._capabilities: Dict[str, Any] = {}
        self._message_endpoint = config.get("message_endpoint", "") or ""

        self._stream_thread: Optional[threading.Thread] = None
        self._stream_response = None
        self._stream_stop = threading.Event()
        self._stream_ready = threading.Event()
        self._endpoint_ready = threading.Event()
        self._stream_error: Optional[BaseException] = None

        self._incoming_messages: "queue.Queue[dict]" = queue.Queue()
        self._buffered_responses: Dict[int, dict] = {}
        self._buffer_lock = threading.Lock()
        self._request_lock = threading.Lock()

    @staticmethod
    def _normalize_timeout(value: Any) -> float:
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            return 30.0
        return timeout if timeout > 0 else 30.0

    @staticmethod
    def _normalize_headers(value: Any) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {str(key): str(item) for key, item in value.items()}

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": "LLM-Tree/1.0",
            **self.headers,
        }
        if extra:
            headers.update(extra)
        return headers

    def _start_stream(self) -> None:
        if self._stream_thread and self._stream_thread.is_alive():
            return

        if not self.endpoint:
            raise ValueError("No endpoint configured for SSE transport.")

        self._stream_stop.clear()
        self._stream_ready.clear()
        self._endpoint_ready.clear()
        self._stream_error = None

        thread = threading.Thread(target=self._run_stream_loop, daemon=True)
        self._stream_thread = thread
        thread.start()

    def _stop_stream(self) -> None:
        self._stream_stop.set()
        if self._stream_response is not None:
            try:
                self._stream_response.close()
            except Exception:
                pass
            self._stream_response = None
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=1)
        self._stream_thread = None
        self._is_initialized = False

    def _run_stream_loop(self) -> None:
        request = urllib.request.Request(
            self.endpoint,
            headers=self._build_headers(
                {
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                }
            ),
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self._stream_response = response
                self._stream_ready.set()
                self._consume_stream(response)
        except Exception as exc:
            self._stream_error = exc
            self._stream_ready.set()
            self._endpoint_ready.set()
        finally:
            self._stream_response = None

    def _consume_stream(self, response) -> None:
        event_name = "message"
        data_lines: List[str] = []

        while not self._stream_stop.is_set():
            raw_line = response.readline()
            if not raw_line:
                if not self._stream_stop.is_set() and self._stream_error is None:
                    self._stream_error = RuntimeError("SSE stream closed unexpectedly.")
                self._endpoint_ready.set()
                return

            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                self._dispatch_sse_event(event_name, data_lines)
                event_name = "message"
                data_lines = []
                continue

            if line.startswith(":"):
                continue

            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]

            if field == "event":
                event_name = value or "message"
            elif field == "data":
                data_lines.append(value)

    def _dispatch_sse_event(self, event_name: str, data_lines: List[str]) -> None:
        if not data_lines:
            return

        payload = "\n".join(data_lines)
        if event_name == "endpoint":
            self._set_message_endpoint(payload)
            return

        try:
            message = json.loads(payload)
        except json.JSONDecodeError as exc:
            self._stream_error = RuntimeError(
                f"Failed to parse JSON from SSE event payload: {payload}"
            )
            self._endpoint_ready.set()
            raise RuntimeError("Invalid SSE JSON payload.") from exc

        self._incoming_messages.put(message)

    def _set_message_endpoint(self, payload: str) -> None:
        endpoint_value = payload.strip()
        if not endpoint_value:
            return

        if endpoint_value.startswith("{"):
            try:
                parsed = json.loads(endpoint_value)
            except json.JSONDecodeError:
                parsed = {}
            endpoint_value = (
                parsed.get("endpoint")
                or parsed.get("url")
                or parsed.get("messageEndpoint")
                or endpoint_value
            )

        self._message_endpoint = urllib.parse.urljoin(self.endpoint, endpoint_value)
        self._endpoint_ready.set()

    def _ensure_stream_connected(self) -> None:
        if self._stream_thread and self._stream_thread.is_alive() and self._message_endpoint:
            return

        self._start_stream()
        if not self._stream_ready.wait(timeout=self.timeout):
            self._stop_stream()
            raise RuntimeError(
                f"Timed out connecting to SSE MCP stream after {self.timeout} seconds."
            )

        if self._stream_error and not self._message_endpoint:
            error = self._stream_error
            self._stop_stream()
            raise RuntimeError(f"Failed to open SSE MCP stream: {error}")

        if self._message_endpoint:
            self._endpoint_ready.set()

        if not self._endpoint_ready.wait(timeout=self.timeout):
            self._stop_stream()
            raise RuntimeError(
                f"Timed out waiting for SSE MCP endpoint announcement after {self.timeout} seconds."
            )

        if not self._message_endpoint:
            error = self._stream_error
            self._stop_stream()
            if error:
                raise RuntimeError(f"SSE MCP stream did not provide a message endpoint: {error}")
            raise RuntimeError("SSE MCP stream did not provide a message endpoint.")

    def _post_jsonrpc(self, payload: Dict[str, Any]) -> None:
        self._ensure_stream_connected()
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._message_endpoint,
            data=data,
            method="POST",
            headers=self._build_headers(
                {
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                }
            ),
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"SSE MCP request failed with HTTP {exc.code}: {body or exc.reason}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to send SSE MCP request: {exc}") from exc

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        with self._request_lock:
            self._request_id += 1
            request_id = self._request_id
            self._post_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            response = self._wait_for_response(request_id)

        if "error" in response:
            error = response["error"]
            raise RuntimeError(
                f"MCP Error {error.get('code')}: {error.get('message')}"
            )
        if "result" not in response:
            raise RuntimeError(
                f"Invalid JSON-RPC response: missing 'result' or 'error' in {response}"
            )
        return response.get("result", {})

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        notification: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params
        self._post_jsonrpc(notification)

    def _wait_for_response(self, request_id: int) -> Dict[str, Any]:
        deadline = time.monotonic() + self.timeout

        while True:
            with self._buffer_lock:
                if request_id in self._buffered_responses:
                    return self._buffered_responses.pop(request_id)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    f"Timed out waiting for SSE MCP response after {self.timeout} seconds."
                )

            try:
                response = self._incoming_messages.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                if (
                    self._stream_error
                    and (self._stream_thread is None or not self._stream_thread.is_alive())
                ):
                    raise RuntimeError(
                        f"SSE MCP stream ended before response arrived: {self._stream_error}"
                    )
                continue

            response_id = response.get("id")
            if response_id == request_id:
                return response
            if response_id is None:
                continue

            with self._buffer_lock:
                self._buffered_responses[response_id] = response

    def _ensure_initialized(self) -> None:
        if self._is_initialized and self._stream_thread and self._stream_thread.is_alive():
            return

        try:
            result = self._request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "LLM-Tree", "version": "1.0.0"},
                },
            )
            self._server_info = result.get("serverInfo", {})
            self._capabilities = result.get("capabilities", {})
            self._notify("notifications/initialized")
            self._is_initialized = True
        except Exception as exc:
            self._stop_stream()
            raise RuntimeError(f"MCP Handshake failed: {exc}") from exc

    def list_tools(self) -> List[ToolDefinition]:
        self._ensure_initialized()
        try:
            result = self._request("tools/list", {})
            tools = []
            for item in result.get("tools", []):
                tools.append(
                    ToolDefinition(
                        name=item.get("name"),
                        description=item.get("description", ""),
                        input_schema=item.get(
                            "inputSchema", {"type": "object", "properties": {}}
                        ),
                    )
                )
            return tools
        except Exception as exc:
            raise RuntimeError(f"Failed to list tools: {exc}") from exc

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        try:
            self._ensure_initialized()
            result = self._request(
                "tools/call",
                {
                    "name": name,
                    "arguments": arguments,
                },
            )
            return ToolResult(
                content=result.get("content", []),
                is_error=result.get("isError", False),
                metadata={
                    "transport": "sse",
                    "server_info": self._server_info,
                    "message_endpoint": self._message_endpoint,
                },
            )
        except Exception as exc:
            return ToolResult.from_error(f"SSE MCP call failed: {exc}")

    def get_server_info(self) -> Dict[str, Any]:
        info = {
            "label": self.server_label,
            "transport": self.transport_kind,
            "endpoint": self.endpoint,
            "message_endpoint": self._message_endpoint,
        }
        if self._is_initialized and self._stream_thread and self._stream_thread.is_alive():
            info["status"] = "connected"
            info["server_info"] = self._server_info
            info["capabilities"] = self._capabilities
            return info

        if self._stream_thread and self._stream_thread.is_alive():
            info["status"] = "connecting"
            return info

        info["status"] = "skeleton" if self.endpoint else "disconnected"
        if self._stream_error:
            info["last_error"] = str(self._stream_error)
        return info

    def __del__(self):
        try:
            self._stop_stream()
        except Exception:
            pass
