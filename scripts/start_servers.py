"""
一键启动双域名服务器
"""
import asyncio
import subprocess
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    """启动 alpha 和 beta 两个服务器实例"""
    python = sys.executable
    server_module = os.path.join(ROOT_DIR, "server", "main.py")
    
    configs = [
        os.path.join(ROOT_DIR, "config", "alpha.yaml"),
        os.path.join(ROOT_DIR, "config", "beta.yaml"),
    ]
    
    processes = []
    
    for config_path in configs:
        print(f"启动服务器: {config_path}")
        proc = subprocess.Popen(
            [python, server_module, config_path],
            cwd=ROOT_DIR
        )
        processes.append(proc)
    
    print("\n双域名服务器已启动：")
    print("  alpha.local -> 127.0.0.1:8001")
    print("  beta.local  -> 127.0.0.1:8002")
    print("\n按 Ctrl+C 停止所有服务器...")
    
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止所有服务器...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        print("所有服务器已停止")


if __name__ == "__main__":
    main()
