"""本地 HTTP CONNECT 代理（开发辅助工具）。

用途：比赛服务器无法直连外网时，通过 SSH 反向隧道（ssh -R 1080:127.0.0.1:1080）
把服务器的流量转发到本机，由本机代理出网。

用法：
    python tools/proxy.py [port]   # 默认 1080，仅监听 127.0.0.1
    ssh -N -R 1080:127.0.0.1:1080 match-server
    服务器上: export http_proxy=http://127.0.0.1:1080 https_proxy=http://127.0.0.1:1080
"""
import socket
import sys
import threading

LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 1080


def _relay(src: socket.socket, dst: socket.socket) -> None:
    """单向转发，直到 EOF。"""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle(client: socket.socket) -> None:
    """处理单个客户端连接：解析 CONNECT 目标并建立隧道。"""
    try:
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = client.recv(4096)
            if not chunk:
                return
            req += chunk
            if len(req) > 65536:
                return

        head = req.split(b"\r\n", 1)[0].decode(errors="ignore")
        parts = head.split()
        if len(parts) < 2:
            return

        method, target = parts[0], parts[1]
        if method.upper() == "CONNECT":
            host, _, port = target.partition(":")
            port = int(port or 443)
        else:
            # 非 CONNECT：解析绝对 URL（http://host:port/path）
            if target.startswith("http://"):
                rest = target[len("http://"):]
                host, _, after = rest.partition("/")
                if ":" in host:
                    host, _, port_str = host.partition(":")
                    port = int(port_str or 80)
                else:
                    port = 80
            else:
                return

        upstream = socket.create_connection((host, port), timeout=15)
        if method.upper() == "CONNECT":
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        else:
            upstream.sendall(req)  # 原样转发原始请求

        t1 = threading.Thread(target=_relay, args=(client, upstream), daemon=True)
        t2 = threading.Thread(target=_relay, args=(upstream, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except OSError:
        pass
    finally:
        try:
            client.close()
        except OSError:
            pass


def main() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LISTEN_PORT))
    srv.listen(50)
    print(f"[proxy] listening on 127.0.0.1:{LISTEN_PORT}", flush=True)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
