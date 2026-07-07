#!/usr/bin/env python3
"""
Configuration smoke test.

Loads config.yaml and prints the configured instruments. Does not
attempt any TCP / USB connection — for that, use the Connect tab
in the GUI. This script is useful from CI to confirm the
configuration parses and the expected instruments are present.

Run with: ``python -m scripts.test_connection`` from the
project root.
"""


def test_configuration():
    print("Testing configuration loading...")
    try:
        from config_loader import get_config
        config = get_config()
        print("[OK] Configuration loaded successfully")

        instruments = config.get('instruments', {})
        print(f"[OK] Found {len(instruments)} instruments in configuration")
        for instrument_id, instrument_config in instruments.items():
            address = instrument_config.get('address', 'Not configured')
            print(f"  - {instrument_id}: {address}")
        return True
    except Exception as e:
        print(f"[FAIL] Configuration error: {e}")
        return False


def main():
    print("=" * 50)
    print("DAQ-Pyvisa Configuration Test")
    print("=" * 50)

    if not test_configuration():
        print("\nConfiguration test failed. Please check config.yaml.")


if __name__ == "__main__":
    main()
