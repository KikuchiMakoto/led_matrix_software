"""LED Matrix Display - Main Entry Point

This script demonstrates how to use the LED Matrix software with the refactored
module structure. It supports static display, single scroll, infinite loop
scrolling, and Dashboard Mode (async weather + train MailLoop).

Usage:
    # Static display
    python main.py --text "Hello"

    # Scroll mode (single scroll)
    python main.py --mode scroll --text "スクロール"

    # Loop mode (infinite loop until Ctrl+C)
    python main.py --mode loop --text "ループ"

    # Dashboard mode (async weather + train MailLoop)
    python main.py --mode dashboard --device terminal
    python main.py --mode dashboard --device serial --port COM5

    # Background mode (resident in the task tray, quit from the tray menu)
    python main.py --bg --mode dashboard --device serial --port COM5
    # To hide the console window on Windows, launch with pythonw:
    #   pythonw main.py --bg --mode dashboard --device serial --port COM5

    # Using different devices
    python main.py --device serial --port COM5 --text "Test"
    python main.py --device terminal --text "Test"
    python main.py --device image --output-dir output --text "Test"

    # Note: For image device, loop mode will behave as scroll mode (single scroll)
    python main.py --device image --mode loop --text "Test"
"""
import argparse
import sys

from src.led_matrix_software.background import is_bg_child, relaunch_detached
from src.led_matrix_software.fonts import ShinonomeFont, CharaZenkakuFont
from src.led_matrix_software.devices import (
    SerialLEDDevice,
    TerminalSimulator,
    ImageSimulator,
    FrameTapDevice,
)
from src.led_matrix_software.main import run_display
from src.led_matrix_software.power import prevent_sleep
from src.led_matrix_software.tray import run_in_tray


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='LED Matrix Display Control',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --text "Hello, World!"
  %(prog)s --mode scroll --text "スクロールテスト"
  %(prog)s --mode loop --text "ループテスト"
  %(prog)s --mode dashboard --device terminal
  %(prog)s --mode dashboard --device serial --port COM5
  %(prog)s --bg --mode dashboard --device serial --port COM5
  %(prog)s --device serial --port COM5 --text "Test"
  %(prog)s --device image --output-dir output --mode scroll --text "動画"
  %(prog)s --device image --output-dir output --mode loop --text "ループ動画"
        """
    )

    # Device options
    parser.add_argument(
        '--device',
        choices=['serial', 'terminal', 'image'],
        default='terminal',
        help='Output device type (default: terminal)'
    )
    parser.add_argument(
        '--port',
        default='COM23',
        help='Serial port (for serial device, default: COM23)'
    )
    parser.add_argument(
        '--baudrate',
        type=int,
        default=921600,
        help='Serial baudrate (default: 921600)'
    )

    # Font options
    parser.add_argument(
        '--font',
        choices=['shinonome', 'chara_zenkaku'],
        default='shinonome',
        help='Font to use (default: shinonome)'
    )
    parser.add_argument(
        '--font-dir',
        help='Font directory path (optional)'
    )

    # Display options
    parser.add_argument(
        '--mode',
        choices=['static', 'scroll', 'loop', 'dashboard'],
        default='static',
        help=(
            'Display mode: static (no scroll), scroll (scroll once), '
            'loop (infinite scroll), dashboard (async weather+train MailLoop). '
            'Default: static'
        )
    )
    parser.add_argument(
        '--text',
        default='Hello, LED!',
        help='Text to display (ignored by dashboard mode)'
    )
    parser.add_argument(
        '--scroll-speed',
        type=float,
        default=0.02,
        help='Scroll speed in seconds (default: 0.02)'
    )

    # Background (task tray) option
    parser.add_argument(
        '--bg',
        action='store_true',
        help=(
            'Run detached in the task tray: the terminal is released immediately '
            'and the display keeps running after it is closed (quit from the tray menu)'
        )
    )
    parser.add_argument(
        '--bg-log',
        default='led_matrix_bg.log',
        help='Log file for --bg output (default: led_matrix_bg.log)'
    )

    # Image output options
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory for image device (default: output)'
    )

    # Dashboard options
    parser.add_argument(
        '--weather-interval',
        type=float,
        default=600.0,
        help='Dashboard mode: seconds between weather fetches (default: 600)'
    )
    parser.add_argument(
        '--train-interval',
        type=float,
        default=60.0,
        help='Dashboard mode: seconds between train fetches (default: 60)'
    )
    parser.add_argument(
        '--alert-scroll-speed',
        type=float,
        default=0.04,
        help='Dashboard mode: scroll delay for alert segments (default: 0.04)'
    )

    args = parser.parse_args()

    # Dashboard mode requires Shinonome (charset coverage of weather/warning terms).
    if args.mode == 'dashboard' and args.font != 'shinonome':
        print(
            "Error: Dashboard mode requires --font shinonome "
            f"(selected: {args.font}). Chara Zenkaku lacks many required glyphs."
        )
        sys.exit(2)

    # --bg: hand over to a detached child and free this terminal immediately.
    if args.bg and not is_bg_child():
        pid, log_path = relaunch_detached(args.bg_log)
        print(f"Running in background (pid {pid}). Quit from the task tray icon.")
        print(f"Log: {log_path}")
        return

    # Initialize font
    print(f"Initializing font: {args.font}")
    if args.font == 'shinonome':
        font_dir = args.font_dir or './shinonome16-1.0.4'
        font = ShinonomeFont(font_dir=font_dir)
    else:  # chara_zenkaku
        font_dir = args.font_dir or './chara_zenkaku'
        font = CharaZenkakuFont(font_dir=font_dir)

    # Initialize device
    print(f"Initializing device: {args.device}")
    if args.device == 'serial':
        try:
            device = SerialLEDDevice(port=args.port, baudrate=args.baudrate)
        except Exception as e:
            print(f"Error: Failed to open serial port {args.port}")
            print(f"Details: {e}")
            print("\nTry using --device terminal for testing without hardware")
            sys.exit(1)
    elif args.device == 'terminal':
        device = TerminalSimulator()
    else:  # image
        device = ImageSimulator(output_dir=args.output_dir)

    try:
        # Keep the PC awake while displaying; screen lock / screen off is allowed.
        with prevent_sleep():
            if args.bg:
                tap = FrameTapDevice(device)
                run_in_tray(
                    lambda stop_event: run_display(args, tap, font, stop_event),
                    title="LED Matrix",
                    status=f"{args.mode} / {args.device}",
                    frame_source=tap.latest_frame,
                )
            else:
                run_display(args, device, font)

    finally:
        device.close()
        print("\nDone!")


if __name__ == '__main__':
    main()
