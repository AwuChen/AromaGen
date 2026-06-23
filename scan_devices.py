#!/usr/bin/env python3
"""
BLE Device Scanner
This script scans for nearby Bluetooth Low Energy devices and displays their information.
"""
import asyncio
import sys
from bleak import BleakScanner

async def scan_devices():
    print("=" * 70)
    print("🔍 BLE DEVICE SCANNER")
    print("=" * 70)
    print("\nScanning for Bluetooth Low Energy devices...")
    print("This may take 10-15 seconds...\n")
    
    try:
        # Scan with longer timeout
        devices = await BleakScanner.discover(timeout=15.0)
        
        if not devices:
            print("❌ No BLE devices found!")
            print("\n⚠️  Troubleshooting:")
            print("  1. Make sure your device is POWERED ON")
            print("  2. Make sure your device is within RANGE (< 10 meters)")
            print("  3. Make sure Bluetooth is ENABLED on your Mac")
            print("  4. Try turning your device OFF and back ON")
            print("  5. Check System Settings > Privacy & Security > Bluetooth")
            print("     - Make sure Terminal/Python has Bluetooth access")
            return
        
        # Filter to only show devices with names (more useful)
        named_devices = [d for d in devices if d.name]
        unnamed_count = len(devices) - len(named_devices)
        
        print(f"✅ Found {len(devices)} device(s) total")
        print(f"   ({len(named_devices)} with names, {unnamed_count} unnamed)")
        print("\n" + "=" * 70)
        print("DEVICES WITH NAMES:")
        print("=" * 70)
        
        if not named_devices:
            print("\n⚠️  No devices with names found!")
            print("Your DeathScent device might not be broadcasting a name.")
            print("\nShowing ALL devices (including unnamed):\n")
            named_devices = devices  # Show all if none have names
        
        for i, device in enumerate(named_devices, 1):
            print(f"\n📱 Device #{i}:")
            print(f"   Name:    {device.name if device.name else '(Unknown/No Name)'}")
            print(f"   Address: {device.address}")
            
            # Try to get RSSI if available
            try:
                if hasattr(device, 'rssi') and device.rssi:
                    print(f"   Signal:  {device.rssi} dBm {'📶' if device.rssi > -70 else '📡'}")
            except:
                pass
            
            # Highlight if it might be the DeathScent device
            if device.name and any(keyword in device.name.lower() for keyword in ['death', 'scent', 'aroma', 'smell', 'olorama', 'olfactory']):
                print(f"   ⭐⭐⭐ THIS MIGHT BE YOUR DEATHSCENT DEVICE! ⭐⭐⭐")
            
            print("-" * 70)
        
        print("\n📝 NEXT STEPS:")
        print("1. Find your DeathScent device in the list above")
        print("2. Copy its Address (the long string of letters/numbers)")
        print("3. Open backend.py in your editor")
        print("4. Find line 9 and replace the BLE_ADDRESS with your device's address:")
        print("   BLE_ADDRESS = \"YOUR-DEVICE-ADDRESS-HERE\"")
        print("5. Save the file and restart the server (python run.py)")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("\n⚠️  This might be a Bluetooth permission issue on macOS.")
        print("\n📋 To fix macOS Bluetooth permissions:")
        print("  1. Open System Settings")
        print("  2. Go to Privacy & Security > Bluetooth")
        print("  3. Make sure Terminal (or your IDE) has Bluetooth access enabled")
        print("  4. You may need to restart Terminal/IDE after enabling")
        print("\nIf that doesn't work, try finding the device address manually:")
        print("  1. Open System Settings > Bluetooth")
        print("  2. Find your device in the list")
        print("  3. The address might be shown in device info")

if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Make sure your DeathScent device is POWERED ON!\n")
    try:
        asyncio.run(scan_devices())
    except KeyboardInterrupt:
        print("\n\n🛑 Scan cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

