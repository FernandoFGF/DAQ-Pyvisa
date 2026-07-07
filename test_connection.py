#!/usr/bin/env python3
"""
Test Connection Script

This script tests the instrument connection functionality without opening the GUI.

Author: Fernando Fuentes-Guerra
Date: 2025
"""

import sys
from pathlib import Path

def test_configuration():
    """Test configuration loading."""
    print("Testing configuration loading...")
    try:
        from config_loader import get_config
        config = get_config()
        print("✓ Configuration loaded successfully")
        
        # Test the get method
        instruments = config.get('instruments', {})
        print(f"✓ Found {len(instruments)} instruments in configuration")
        
        for instrument_id, instrument_config in instruments.items():
            address = instrument_config.get('address', 'Not configured')
            print(f"  - {instrument_id}: {address}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_instrument_connection():
    """Test instrument connection."""
    print("\nTesting instrument connection...")
    try:
        from gui_functions import DAQGUIFunctions
        
        gui_funcs = DAQGUIFunctions()
        
        # Test connection
        gui_funcs.connect_all_instruments()
        
        # Get status
        status = gui_funcs.get_instrument_status()
        print(f"✓ Instrument status retrieved: {len(status)} instruments")
        
        # Cleanup
        gui_funcs.cleanup()
        print("✓ Cleanup completed")
        
        return True
    except Exception as e:
        print(f"✗ Connection test error: {e}")
        return False

def main():
    """Main test function."""
    print("=" * 50)
    print("DAQ-Pyvisa Connection Test")
    print("=" * 50)
    
    # Test configuration
    config_ok = test_configuration()
    
    if not config_ok:
        print("\n❌ Configuration test failed. Please check config.yaml")
        return
    
    # Test connection
    connection_ok = test_instrument_connection()
    
    if connection_ok:
        print("\n✅ All tests passed!")
        print("\nNote: If instruments show as 'not connected', this is normal if:")
        print("1. Instruments are not powered on")
        print("2. Network connections are not established")
        print("3. IP addresses in config.yaml are incorrect")
        print("4. VISA drivers are not installed")
    else:
        print("\n❌ Connection test failed. Check the error messages above.")

if __name__ == "__main__":
    main()
