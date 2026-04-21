"""
一键启动全部服务：后端 + WebSocket 网关 + 前端开发服务器
"""
import subprocess
import sys
import os
import platform

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT_DIR, "web")


def main():
    """启动 alpha/beta 后端 + WS 网关 + 前端 dev server"""
    python = sys.executable
    server_module = os.path.join(ROOT_DIR, "server", "main.py")
    ws_gateway = os.path.join(ROOT_DIR, "server", "ws_gateway.py")

    # npm/npx 在 Windows 上需要 shell=True
    is_windows = platform.system() == "Windows"

    processes = []

    # 1. 后端服务器（alpha + beta）
    for config_name in ("alpha", "beta"):
        config_path = os.path.join(ROOT_DIR, "config", f"{config_name}.yaml")
        print(f"[后端] 启动 {config_name}: {config_path}")
        proc = subprocess.Popen(
            [python, server_module, config_path],
            cwd=ROOT_DIR,
        )
        processes.append(proc)

    # 2. WebSocket 网关（alpha + beta）
    for config_name in ("alpha", "beta"):
        config_path = os.path.join(ROOT_DIR, "config", f"{config_name}.yaml")
        print(f"[WS网关] 启动 {config_name}: {config_path}")
        proc = subprocess.Popen(
            [python, ws_gateway, config_path],
            cwd=ROOT_DIR,
        )
        processes.append(proc)

    # 3. 前端开发服务器（alpha 端口 5173）
    print("[前端] 启动 alpha dev server (端口 5173)")
    proc = subprocess.Popen(
        ["npx", "vite", "--mode", "alpha"],
        cwd=WEB_DIR,
        shell=is_windows,
    )
    processes.append(proc)

    # 4. 前端开发服务器（beta 端口 5174）
    print("[前端] 启动 beta dev server (端口 5174)")
    proc = subprocess.Popen(
        ["npx", "vite", "--mode", "beta", "--port", "5174"],
        cwd=WEB_DIR,
        shell=is_windows,
    )
    processes.append(proc)

    print("\n" + "=" * 60)
    print("  SafeEmail 全部服务已启动")
    print("=" * 60)
    print("  后端：")
    print("    alpha.local -> 127.0.0.1:8001")
    print("    beta.local  -> 127.0.0.1:8002")
    print("  WebSocket 网关：")
    print("    alpha WS -> ws://127.0.0.1:3001")
    print("    beta  WS -> ws://127.0.0.1:3002")
    print("  前端：")
    print("    alpha 前端 -> http://localhost:5173")
    print("    beta  前端 -> http://localhost:5174")
    print("=" * 60)
    print("\n按 Ctrl+C 停止所有服务...")

    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止所有服务...")
        for proc in processes:
            try:
                proc.terminate()
            except OSError:
                pass
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("所有服务已停止")


if __name__ == "__main__":
    main()
