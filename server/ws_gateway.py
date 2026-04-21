"""
WebSocket 网关 — 浏览器 ↔ TCP 协议桥接

用法:
    python server/ws_gateway.py config/alpha.yaml
    python server/ws_gateway.py config/beta.yaml
"""

import asyncio
import ssl
import sys
import os
import logging

import yaml

try:
    import websockets
    from websockets.asyncio.server import serve
except ImportError:
    print("请安装 websockets: pip install websockets")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('ws_gateway')


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_ssl_context(config: dict) -> ssl.SSLContext:
    """创建到后端的 TLS 客户端上下文"""
    tls_conf = config['tls']
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.load_verify_locations(tls_conf['ca_file'])
    # 开发环境：不验证主机名
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


async def ws_to_tcp(websocket, tcp_writer, peer: str):
    """浏览器 → 后端"""
    try:
        async for message in websocket:
            if isinstance(message, str):
                tcp_writer.write(message.encode('utf-8') + b'\r\n')
                await tcp_writer.drain()
    except Exception as e:
        logger.debug(f"[{peer}] WS→TCP 结束: {e}")
    finally:
        tcp_writer.close()


async def tcp_to_ws(tcp_reader, websocket, peer: str):
    """后端 → 浏览器"""
    try:
        while True:
            data = await tcp_reader.readline()
            if not data:
                break
            text = data.decode('utf-8').strip()
            if text:
                await websocket.send(text)
    except Exception as e:
        logger.debug(f"[{peer}] TCP→WS 结束: {e}")


async def handle_websocket(websocket, backend_host: str, backend_port: int, ssl_ctx: ssl.SSLContext):
    """处理单个 WebSocket 连接"""
    peer = str(websocket.remote_address) if hasattr(websocket, 'remote_address') else 'unknown'
    logger.info(f"[{peer}] 新 WebSocket 连接")

    try:
        # 建立到后端的 TCP+TLS 连接
        tcp_reader, tcp_writer = await asyncio.open_connection(
            backend_host, backend_port, ssl=ssl_ctx,
        )
        logger.info(f"[{peer}] TCP 连接已建立 → {backend_host}:{backend_port}")

        # 双向透传
        await asyncio.gather(
            ws_to_tcp(websocket, tcp_writer, peer),
            tcp_to_ws(tcp_reader, websocket, peer),
        )
    except ConnectionRefusedError:
        logger.error(f"[{peer}] 无法连接后端 {backend_host}:{backend_port}")
        try:
            await websocket.close(1011, "后端服务不可用")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[{peer}] 连接异常: {e}")
    finally:
        logger.info(f"[{peer}] 连接关闭")


async def main(config_path: str):
    config = load_config(config_path)

    # WebSocket 网关配置
    ws_conf = config.get('ws_gateway', {})
    ws_host = ws_conf.get('host', '127.0.0.1')
    ws_port = ws_conf.get('port', 3001)

    # 后端 TCP 配置
    server_conf = config['server']
    backend_host = server_conf['host']
    backend_port = server_conf['port']

    # TLS 上下文（连接后端用）
    ssl_ctx = create_ssl_context(config)

    domain = server_conf.get('domain', 'unknown')
    logger.info(f"WebSocket 网关启动: ws://{ws_host}:{ws_port}")
    logger.info(f"  域名: {domain}")
    logger.info(f"  后端: {backend_host}:{backend_port} (TLS)")

    async def handler(websocket):
        await handle_websocket(websocket, backend_host, backend_port, ssl_ctx)

    async with serve(handler, ws_host, ws_port):
        logger.info(f"网关就绪，等待连接...")
        await asyncio.Future()  # 永久运行


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <config.yaml>")
        print(f"示例: python {sys.argv[0]} config/alpha.yaml")
        sys.exit(1)

    config_path = sys.argv[1]
    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)

    try:
        asyncio.run(main(config_path))
    except KeyboardInterrupt:
        logger.info("网关已停止")
