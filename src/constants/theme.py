######## LIBRARIES ########

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
from rich.table import Table
from enum import Enum, auto
from pathlib import Path


######## VERSIONING ########

def getVersion() -> str:
    try:
        return version("spicebag")

    except PackageNotFoundError:
        return "1.0.0"


######## CONSTANTS ########

WORD_COUNTS = [12, 15, 18, 20, 21, 24, 33]

COMMANDS = ["encode", "decode", "clear", "banner", "help", "exit"]

GRID_SIZES = {
    12: (3, 4),
    15: (3, 5),
    18: (3, 6),
    20: (4, 5),
    21: (3, 7),
    24: (4, 6),
    33: (3, 11)
}

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

OUTPUT_DIR = Path.home() / "Spicebag"

ASCII_ART_BANNER = """
                                                                          
                                              █████                       
  █████████                                  ░░███                        
 ███░░░░░███                                  ░███                     ███
░███    ░░░  ████████  ████   ██████   ██████ ░███████   ██████    ██████ 
░░█████████ ░░███░░███░░███  ███░░███ ███░░███░███░░███ ░░░░░███  ███░░███
 ░░░░░░░░███ ░███ ░███ ░███ ░███ ░░░ ░███████ ░███ ░███  ███████ ░███ ░███
 ███    ░███ ░███ ░███ ░███ ░███  ███░███░░░  ░███ ░███ ███░░███ ░░██████ 
░░█████████  ░███████  █████░░██████ ░░██████ ████████ ░░████████ ░░██░░  
 ░░░░░░░░░   ░███░░░  ░░░░░  ░░░░░░   ░░░░░░ ░░░░░░░░   ░░░░░░░░  ███████ 
             ░███                                                ███░░░███
             █████                                              ░███  ░███
            ░░░░░                                               ░░███████ 
                                                                 ░░░░░░░  
                                                                          
"""


def getGradientString(text: str) -> str:
    import colorsys
    result = ""
    maxW = len(text)
    for x, char in enumerate(text):
        if char.isspace():
            result += char
            continue

        t = x / max(1, maxW - 1)
        h = (G_START[0] + (G_END[0] - G_START[0]) * t) % 1.0
        light = G_START[1] + (G_END[1] - G_START[1]) * t
        s = G_START[2] + (G_END[2] - G_START[2]) * t

        r, g, b = colorsys.hls_to_rgb(h, light, s)
        hexColor = f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"
        result += f"[{hexColor}]{char}[/]"
    return result



######## MASCOT CONFIGURATION ########

MASCOT_BANNER = [
    " ▂▂ ▂ ▂ ▂ ",
    " ████████ ",
    "██████████",
    "██████████",
    " ▀▀▀▀▀▀▀▀ "
]

MASCOT_COLORS = [
    [     None, "#945321", "#BF8C54",      None, "#BF8C54",      None, "#BF8C54",      None, "#BF8C54",      None],
    [     None, "#945321", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54",      None],
    ["#645166", "#645166", "#FFE390", "#FFE390", "#68734C", "#68734C", "#FCB1A8", "#FCB1A8", "#485870", "#485870"],
    ["#645166", "#645166", "#FFE390", "#FFE390", "#68734C", "#68734C", "#FCB1A8", "#FCB1A8", "#485870", "#485870"],
    [     None, "#945321", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54", "#BF8C54",      None],
]


def _winAdapterState() -> tuple[bool, bool]:
    import ctypes
    from ctypes import wintypes

    AF_UNSPEC = 0
    IF_TYPE_ETHERNET = 6
    IF_TYPE_WIFI = 71
    OPER_STATUS_UP = 1

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
            if node.OperStatus == OPER_STATUS_UP:
                if node.IfType == IF_TYPE_ETHERNET:
                    isEthernet = True
                elif node.IfType == IF_TYPE_WIFI:
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

    def runLocal(args: list[str]) -> str:
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=2).stdout
        except Exception:
            return ""

    isBluetooth = False
    btState = runLocal(["defaults", "read", "/Library/Preferences/com.apple.Bluetooth", "ControllerPowerState"])
    if btState.strip() == "1":
        isBluetooth = True

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


def getNetworkText(net_state: tuple[bool, bool, bool]) -> str:
    isEthernet, isWifi, isBluetooth = net_state
    isOnline = isEthernet or isWifi or isBluetooth

    if not isOnline:
        return f"[{C_WHITE}]Network status: [/][bold {C_SUCC}]Offline[/]"

    indicators = []
    if isEthernet:
        indicators.append("Ethernet")
    elif isWifi:
        indicators.append("Wi-Fi")
    if isBluetooth:
        indicators.append("Bluetooth")

    text = f"[{C_WHITE}]Network status: [/][bold {C_FAIL}]Online[/]"
    for indicator in indicators:
        text += f"[{C_DIM}]  ·  {indicator}[/]"

    return text


def getMascotBanner(net_state: tuple[bool, bool, bool] = (False, False, False)) -> Table:
    from rich.text import Text

    table = Table.grid(padding=(0, 3))
    table.add_column(width=12, no_wrap=True)
    table.add_column()

    indentedRows = []
    for y in range(5):
        rowStr = "  "
        for x in range(10):
            char = MASCOT_BANNER[y][x]
            color = MASCOT_COLORS[y][x]
            if color:
                rowStr += f"[{color}]{char}[/]"
            else:
                rowStr += char
        indentedRows.append(rowStr)

    mascot = "\n".join(indentedRows)

    right = (
        "\n"
        f"[bold]{getGradientString('Spicebag')}[/] [{C_DIM}][italic]v{getVersion()}[/][/]\n"
        f"[{C_WHITE}]Visual Mnemonic Encoder / Decoder[/]\n"
        f"{getNetworkText(net_state)}"
    )

    table.add_row(Text.from_markup(mascot), Text.from_markup(right))
    return table

C_BG = "#252525"
C_DIM = "#909090"
C_INP = "#ECD251"
C_IMG = "#88A4E9"
C_WC = "#D787EF"
C_SUCC = "#5DE073"
C_FAIL = "#FF4F5E"
C_WHITE = "#FFFFFF"

G_START = ((360 + 50) / 360, 0.5, 0.62)
G_END = (350 / 360, 0.6, 0.62)

BANNER_META = (
    f"[{C_WHITE}]Visual Mnemonic Encoder / Decoder[/] [{C_DIM}][italic]v{getVersion()}[/]"
)

CLIPBOARD_KEYS = frozenset({
    "ctrl+c", "ctrl+x", "ctrl+v", "ctrl+a", "ctrl+z", "ctrl+insert",
    "shift+insert", "shift+delete",
    "shift+left", "shift+right", "shift+home", "shift+end",
    "ctrl+shift+left", "ctrl+shift+right",
    "ctrl+shift+home", "ctrl+shift+end",
    "cmd+c", "cmd+x", "cmd+v", "cmd+a",
})


######## WORKFLOW STATE ########

class AppState(Enum):
    IDLE = auto()
    ENCODE_COUNT = auto()
    ENCODE_WORD_COUNT = auto()
    ENCODE_PHRASE = auto()
    ENCODE_SALT = auto()
    ENCODE_CELL = auto()
    ENCODE_SAVE_PATH = auto()
    ENCODE_CONFIRM = auto()
    DECODE_PATH = auto()
    DECODE_SALT = auto()
    DECODE_CONFIRM = auto()
    BANNER_CONFIRM = auto()


######## UTILITIES ########

def blendHexColors(c1: str, c2: str, ratio: float) -> str:
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02X}{g:02X}{b:02X}"


def gradientColor(ratio: float) -> str:
    import colorsys
    ratio = max(0.0, min(1.0, ratio))
    h1, s1, v1 = colorsys.rgb_to_hsv(
        int(C_FAIL[1:3], 16) / 255, int(C_FAIL[3:5], 16) / 255, int(C_FAIL[5:7], 16) / 255
    )
    h2, s2, v2 = colorsys.rgb_to_hsv(
        int(C_SUCC[1:3], 16) / 255, int(C_SUCC[3:5], 16) / 255, int(C_SUCC[5:7], 16) / 255
    )
    dh = h2 - h1

    if dh > 0.5:
        dh -= 1.0
    elif dh < -0.5:
        dh += 1.0

    h = (h1 + dh * ratio) % 1.0
    s = s1 + (s2 - s1) * ratio
    v = v1 + (v2 - v1) * ratio

    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def bannerGradientHex(t: float) -> str:
    import colorsys
    t = max(0.0, min(1.0, t))
    h = (G_START[0] + (G_END[0] - G_START[0]) * t) % 1.0
    light = G_START[1] + (G_END[1] - G_START[1]) * t
    s = G_START[2] + (G_END[2] - G_START[2]) * t

    r, g, b = colorsys.hls_to_rgb(h, light, s)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"
