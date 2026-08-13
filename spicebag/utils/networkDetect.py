######## NETWORK DETECTION ########

def _winAdapterState() -> tuple[bool, bool]:
    import ctypes
    from ctypes import wintypes

    AF_UNSPEC = 0
    IF_TYPE_ETHERNET = 6
    IF_TYPE_WIFI = 71
    MEDIA_CONNECTED = 1
    CONNECTOR_PRESENT = 0x04

    class IP_ADAPTER_ADDRESSES(ctypes.Structure):
        pass

    IP_ADAPTER_ADDRESSES._fields_ = [
        ("Length", wintypes.ULONG),
        ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
        ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.c_void_p),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", wintypes.LPWSTR),
        ("Description", wintypes.LPWSTR),
        ("FriendlyName", wintypes.LPWSTR),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.DWORD),
        ("Flags", wintypes.DWORD),
        ("Mtu", wintypes.DWORD),
        ("IfType", wintypes.DWORD),
        ("OperStatus", wintypes.DWORD)
    ]

    # Trailing _tail over-allocates past MediaConnectState so GetIfEntry2 (which
    # writes the full MIB_IF_ROW2) never runs off the end of our buffer.
    class MIB_IF_ROW2(ctypes.Structure):
        _fields_ = [
            ("InterfaceLuid", ctypes.c_ulonglong),
            ("InterfaceIndex", wintypes.DWORD),
            ("InterfaceGuid", ctypes.c_byte * 16),
            ("Alias", ctypes.c_wchar * 257),
            ("Description", ctypes.c_wchar * 257),
            ("PhysicalAddressLength", wintypes.ULONG),
            ("PhysicalAddress", ctypes.c_ubyte * 32),
            ("PermanentPhysicalAddress", ctypes.c_ubyte * 32),
            ("Mtu", wintypes.ULONG),
            ("Type", wintypes.ULONG),
            ("TunnelType", ctypes.c_int),
            ("MediaType", ctypes.c_int),
            ("PhysicalMediumType", ctypes.c_int),
            ("AccessType", ctypes.c_int),
            ("DirectionType", ctypes.c_int),
            ("InterfaceAndOperStatusFlags", ctypes.c_ubyte),
            ("OperStatus", ctypes.c_int),
            ("AdminStatus", ctypes.c_int),
            ("MediaConnectState", ctypes.c_int),
            ("_tail", ctypes.c_ubyte * 512)
        ]

    getIfEntry2 = ctypes.windll.Iphlpapi.GetIfEntry2

    def physicalLink(ifIndex: int, requireConnector: bool) -> bool:
        row = MIB_IF_ROW2()
        row.InterfaceIndex = ifIndex
        if getIfEntry2(ctypes.byref(row)) != 0:
            return False

        if row.MediaConnectState != MEDIA_CONNECTED:
            return False

        connectorPresent = bool(row.InterfaceAndOperStatusFlags & CONNECTOR_PRESENT)
        return connectorPresent or not requireConnector

    getAdapters = ctypes.windll.Iphlpapi.GetAdaptersAddresses
    size = wintypes.ULONG(0)
    getAdapters(AF_UNSPEC, 0, None, None, ctypes.byref(size))

    buf = ctypes.create_string_buffer(size.value)
    head = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
    ret = getAdapters(AF_UNSPEC, 0, None, head, ctypes.byref(size))

    isEthernet = False
    isWifi = False

    if ret == 0:
        cur = head
        while cur:
            node = cur.contents
            if node.IfType == IF_TYPE_ETHERNET and physicalLink(node.IfIndex, True):
                isEthernet = True

            elif node.IfType == IF_TYPE_WIFI and physicalLink(node.IfIndex, False):
                isWifi = True

            cur = node.Next

    return (isEthernet, isWifi)


def _winBluetoothState() -> bool:
    import ctypes
    from ctypes import wintypes

    class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD)]

    try:
        bth = ctypes.windll.LoadLibrary("Bthprops.cpl")

    except OSError:
        return False

    bth.BluetoothFindFirstRadio.restype = wintypes.HANDLE
    bth.BluetoothFindFirstRadio.argtypes = [
        ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS), ctypes.POINTER(wintypes.HANDLE)
    ]
    bth.BluetoothFindRadioClose.argtypes = [wintypes.HANDLE]

    params = BLUETOOTH_FIND_RADIO_PARAMS(ctypes.sizeof(BLUETOOTH_FIND_RADIO_PARAMS))
    radio = wintypes.HANDLE()
    hFind = bth.BluetoothFindFirstRadio(ctypes.byref(params), ctypes.byref(radio))

    if hFind:
        ctypes.windll.kernel32.CloseHandle(radio)
        bth.BluetoothFindRadioClose(hFind)
        return True

    return False


def getNetworkState() -> tuple[bool, bool, bool]:
    import sys

    if sys.platform == "win32":
        isEthernet, isWifi = _winAdapterState()
        isBluetooth = _winBluetoothState()

        return (isEthernet, isWifi, isBluetooth)

    if sys.platform == "linux":
        import os

        netBase = "/sys/class/net"
        isEthernet = False
        isWifi = False
        try:
            for iface in os.listdir(netBase):
                if iface == "lo":
                    continue

                ifacePath = os.path.join(netBase, iface)
                isWireless = os.path.isdir(os.path.join(ifacePath, "wireless"))
                try:
                    with open(os.path.join(ifacePath, "operstate")) as f:
                        isUp = f.read().strip() == "up"

                except OSError:
                    isUp = False

                if not isUp:
                    continue

                if isWireless:
                    isWifi = True

                else:
                    isEthernet = True

        except Exception:
            pass

        isBluetooth = False
        rfkillBase = "/sys/class/rfkill"
        try:
            radios = os.listdir(rfkillBase) if os.path.isdir(rfkillBase) else []
            for entry in radios:
                entryPath = os.path.join(rfkillBase, entry)
                try:
                    with open(os.path.join(entryPath, "type")) as f:
                        if f.read().strip() != "bluetooth":
                            continue

                    with open(os.path.join(entryPath, "state")) as f:
                        if f.read().strip() == "1":
                            isBluetooth = True
                            break

                except OSError:
                    continue

        except Exception:
            pass

        return (isEthernet, isWifi, isBluetooth)

    import subprocess
    import plistlib

    def runLocal(args: list[str]) -> str:
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=2).stdout

        except Exception:
            return ""

    isBluetooth = False
    try:
        with open("/Library/Preferences/com.apple.Bluetooth.plist", "rb") as f:
            isBluetooth = plistlib.load(f).get("ControllerPowerState") == 1

    except Exception:
        isBluetooth = False

    hardwarePorts = runLocal(["networksetup", "-listallhardwareports"]).splitlines()
    wifiDevice = ""

    for i, line in enumerate(hardwarePorts):
        if "Wi-Fi" in line or "AirPort" in line:
            for j in range(i + 1, min(i + 4, len(hardwarePorts))):
                if "Device:" in hardwarePorts[j]:
                    wifiDevice = hardwarePorts[j].split("Device:")[1].strip()
                    break

            break

    isWifi = False
    if len(wifiDevice) > 0 and ": On" in runLocal(["networksetup", "-getairportpower", wifiDevice]):
        isWifi = True

    isEthernet = False
    currentIface = ""
    for line in runLocal(["ifconfig"]).splitlines():
        if line and not line[0].isspace():
            currentIface = line.split(":")[0]

        elif "status: active" in line and currentIface and currentIface != wifiDevice:
            if not currentIface.startswith("lo"):
                isEthernet = True

    return (isEthernet, isWifi, isBluetooth)