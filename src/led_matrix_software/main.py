"""LED Matrix Display Main Program"""

import argparse
import time
import sys

import numpy as np

from .dashboard import DashboardMailLoop, DashboardState
from .fonts import ShinonomeFont, CharaZenkakuFont
from .devices import SerialLEDDevice, TerminalSimulator, ImageSimulator
from .matrix import make_matrix_buffer


def show_text(device, font, text: str):
    """
    Display static text on LED matrix.

    Args:
        device: LED device instance
        font: Font renderer instance
        text: Text to display
    """
    img = font.render_string(text)
    matrix = make_matrix_buffer(img)
    device.write(matrix)


def scroll_text(device, font, text: str, scroll_speed: float = 0.02):
    """
    Scroll text across LED matrix once.

    Args:
        device: LED device instance
        font: Font renderer instance
        text: Text to scroll
        scroll_speed: Delay between frames in seconds (default: 0.02)

    The scroll will run once through the text and stop.
    """
    # Add padding spaces
    padding = "                "
    padded_text = padding + text + padding

    print("Starting single scroll...")
    # Render text once
    img = font.render_string(padded_text)

    # Scroll by removing one column at a time
    loop_length = img.shape[1]
    for i in range(loop_length):
        matrix = make_matrix_buffer(img)
        device.write(matrix)
        img = np.delete(img, 0, axis=1)
        time.sleep(scroll_speed)

    print("Scroll completed.")


def loop_text(device, font, text: str, scroll_speed: float = 0.02):
    """
    Scroll text across LED matrix infinitely.

    Args:
        device: LED device instance
        font: Font renderer instance
        text: Text to scroll
        scroll_speed: Delay between frames in seconds (default: 0.02)

    The scroll will loop infinitely until interrupted with Ctrl+C.
    """
    # Add padding spaces
    padding = "                "
    padded_text = padding + text + padding

    try:
        print("Starting infinite loop scroll... Press Ctrl+C to stop.")
        while True:
            # Render text for each loop iteration
            img = font.render_string(padded_text)

            # Scroll by removing one column at a time
            loop_length = img.shape[1]
            for i in range(loop_length):
                matrix = make_matrix_buffer(img)
                device.write(matrix)
                img = np.delete(img, 0, axis=1)
                time.sleep(scroll_speed)
    except KeyboardInterrupt:
        print("\nLoop scroll stopped by user.")


def dashboard_text(
    device,
    font,
    *,
    weather_interval: float = 600.0,
    train_interval: float = 60.0,
    scroll_speed: float = 0.02,
    alert_scroll_speed: float = 0.04,
) -> None:
    """Run the asynchronous Dashboard Mode MailLoop."""
    state = DashboardState()
    loop = DashboardMailLoop(
        device,
        font,
        state,
        weather_interval=weather_interval,
        train_interval=train_interval,
        scroll_speed=scroll_speed,
        alert_scroll_speed=alert_scroll_speed,
    )
    print(
        "Starting Dashboard Mode (weather every "
        f"{int(weather_interval)}s, trains every {int(train_interval)}s). "
        "Press Ctrl+C to stop."
    )
    loop.start()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="LED Matrix Display Control")

    # Device options
    parser.add_argument(
        "--device",
        choices=["serial", "terminal", "image"],
        default="terminal",
        help="Output device type (default: terminal)",
    )
    parser.add_argument(
        "--port", default="COM23", help="Serial port (for serial device, default: COM23)"
    )
    parser.add_argument(
        "--baudrate", type=int, default=921600, help="Serial baudrate (default: 921600)"
    )

    # Font options
    parser.add_argument(
        "--font",
        choices=["shinonome", "chara_zenkaku"],
        default="shinonome",
        help="Font to use (default: shinonome)",
    )
    parser.add_argument("--font-dir", help="Font directory path (optional)")

    # Display options
    parser.add_argument(
        "--mode",
        choices=["static", "scroll", "loop", "dashboard"],
        default="static",
        help=(
            "Display mode: static (no scroll), scroll (scroll once), "
            "loop (infinite scroll), dashboard (async weather+train MailLoop). "
            "Default: static"
        ),
    )
    parser.add_argument(
        "--text", default="Hello, LED!", help="Text to display (ignored by dashboard mode)"
    )
    parser.add_argument(
        "--scroll-speed", type=float, default=0.02, help="Scroll speed in seconds (default: 0.02)"
    )

    # Image output options
    parser.add_argument(
        "--output-dir", default="output", help="Output directory for image device (default: output)"
    )

    # Dashboard options
    parser.add_argument(
        "--weather-interval",
        type=float,
        default=600.0,
        help="Dashboard mode: seconds between weather fetches (default: 600)",
    )
    parser.add_argument(
        "--train-interval",
        type=float,
        default=60.0,
        help="Dashboard mode: seconds between train fetches (default: 60)",
    )
    parser.add_argument(
        "--alert-scroll-speed",
        type=float,
        default=0.04,
        help="Dashboard mode: scroll delay for alert segments (default: 0.04)",
    )

    args = parser.parse_args()

    # Dashboard mode requires Shinonome (charset coverage of weather/warning terms).
    if args.mode == "dashboard" and args.font != "shinonome":
        print(
            "Error: Dashboard mode requires --font shinonome "
            f"(selected: {args.font}). Chara Zenkaku lacks many required glyphs."
        )
        sys.exit(2)

    # Initialize font
    print(f"Initializing font: {args.font}")
    if args.font == "shinonome":
        font_dir = args.font_dir or "./shinonome16-1.0.4"
        font = ShinonomeFont(font_dir=font_dir)
    else:  # chara_zenkaku
        font_dir = args.font_dir or "./chara_zenkaku"
        font = CharaZenkakuFont(font_dir=font_dir)

    # Initialize device
    print(f"Initializing device: {args.device}")
    if args.device == "serial":
        try:
            device = SerialLEDDevice(port=args.port, baudrate=args.baudrate)
        except Exception as e:
            print(f"Error: Failed to open serial port {args.port}")
            print(f"Details: {e}")
            print("\nTry using --device terminal for testing without hardware")
            sys.exit(1)
    elif args.device == "terminal":
        device = TerminalSimulator()
    else:  # image
        device = ImageSimulator(output_dir=args.output_dir)

    try:
        if args.mode == "static":
            print(f"Displaying text: {args.text}")
            show_text(device, font, args.text)
            if args.device == "terminal":
                print("\nPress Ctrl+C to exit...")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
        elif args.mode == "scroll":
            print(f"Scrolling text: {args.text}")
            scroll_text(device, font, args.text, scroll_speed=args.scroll_speed)
        elif args.mode == "loop":
            print(f"Looping text: {args.text}")
            if args.device == "image":
                print("Image device detected: loop mode will behave as scroll mode (single scroll)")
                scroll_text(device, font, args.text, scroll_speed=args.scroll_speed)
            else:
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


if __name__ == "__main__":
    main()
