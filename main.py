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

    # Using different devices
    python main.py --device serial --port COM5 --text "Test"
    python main.py --device terminal --text "Test"
    python main.py --device image --output-dir output --text "Test"

    # Note: For image device, loop mode will behave as scroll mode (single scroll)
    python main.py --device image --mode loop --text "Test"
"""
import argparse
import sys

from src.led_matrix_software.fonts import ShinonomeFont, CharaZenkakuFont
from src.led_matrix_software.devices import SerialLEDDevice, TerminalSimulator, ImageSimulator
from src.led_matrix_software.main import show_text, scroll_text, loop_text, dashboard_text


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
        # Display text
        if args.mode == 'static':
            print(f"Displaying text: {args.text}")
            show_text(device, font, args.text)
            if args.device == 'terminal':
                print("\nPress Ctrl+C to exit...")
                try:
                    import time
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
        elif args.mode == 'scroll':
            print(f"Scrolling text: {args.text}")
            scroll_text(device, font, args.text, scroll_speed=args.scroll_speed)
        elif args.mode == 'loop':
            # For image device, loop mode behaves as scroll mode (single scroll)
            if args.device == 'image':
                print("Image device detected: loop mode will behave as scroll mode (single scroll)")
                scroll_text(device, font, args.text, scroll_speed=args.scroll_speed)
            else:
                print(f"Looping text: {args.text}")
                loop_text(device, font, args.text, scroll_speed=args.scroll_speed)
        else:  # dashboard
            dashboard_text(
                device,
                font,
                weather_interval=args.weather_interval,
                train_interval=args.train_interval,
                scroll_speed=args.scroll_speed,
                alert_scroll_speed=args.alert_scroll_speed,
            )

    finally:
        device.close()
        print("\nDone!")


if __name__ == '__main__':
    main()
