"""Command line entry point: python -m spot_glass {spot,thermal} [--tunnel]"""

import argparse
import os

from .capture import FrameBuffer, start_capture
from .config import ServerSettings, env_str, load_dotenv
from .server import create_app

# Default port and URL prefix per source. The Spot relay sits under /spot so
# both relays can share one tunnel hostname.
DEFAULTS = {
    "spot": (21001, "/spot"),
    "thermal": (5000, ""),
}


def build_source(kind):
    if kind == "spot":
        from .spot import SpotSource, prompt_for_credentials

        prompt_for_credentials()
        return SpotSource.from_env()

    from .rtsp import RtspSource

    return RtspSource.from_env()


def main():
    parser = argparse.ArgumentParser(
        prog="python -m spot_glass", description="Relay a Spot camera feed as MJPEG."
    )
    parser.add_argument("source", choices=sorted(DEFAULTS), help="camera to relay")
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="also run the Cloudflare tunnel named by CLOUDFLARE_TUNNEL",
    )
    args = parser.parse_args()

    load_dotenv()
    settings = ServerSettings.from_env(*DEFAULTS[args.source])
    source = build_source(args.source)
    buffer = FrameBuffer()
    start_capture(source, buffer, settings)
    app = create_app(source, buffer, settings)

    tunnel = None
    if args.tunnel:
        from .tunnel import Tunnel

        name = env_str("CLOUDFLARE_TUNNEL", "")
        if not name:
            raise SystemExit("--tunnel needs CLOUDFLARE_TUNNEL set (see .env.example)")
        tunnel = Tunnel(name)

    print(
        f"[relay] {source.label} on http://{settings.listen_host}:{settings.listen_port}"
        f"{settings.url_prefix}/view",
        flush=True,
    )
    if os.environ.get("STREAM_HOSTNAME"):
        print(
            f"[relay] public: https://{os.environ['STREAM_HOSTNAME']}{settings.url_prefix}/view",
            flush=True,
        )

    try:
        app.run(host=settings.listen_host, port=settings.listen_port, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel:
            tunnel.stop()


if __name__ == "__main__":
    main()
