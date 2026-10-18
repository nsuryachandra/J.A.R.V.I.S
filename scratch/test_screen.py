import ctypes
from PIL import Image

def capture_screen():
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hDesktopWnd = user32.GetDesktopWindow()
    width = user32.GetSystemMetrics(0)
    height = user32.GetSystemMetrics(1)
    print(f"Desktop size: {width}x{height}")

    hDesktopDC = user32.GetDC(hDesktopWnd)
    hCaptureDC = gdi32.CreateCompatibleDC(hDesktopDC)
    hCaptureBitmap = gdi32.CreateCompatibleBitmap(hDesktopDC, width, height)
    gdi32.SelectObject(hCaptureDC, hCaptureBitmap)

    # BitBlt from desktop to bitmap
    res = gdi32.BitBlt(hCaptureDC, 0, 0, width, height, hDesktopDC, 0, 0, 0x00CC0020)
    print(f"BitBlt result: {res}")

    user32.ReleaseDC(hDesktopWnd, hDesktopDC)
    gdi32.DeleteDC(hCaptureDC)
    gdi32.DeleteObject(hCaptureBitmap)
    return res != 0

if __name__ == "__main__":
    capture_screen()
